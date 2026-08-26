"""Typed, immutable startup configuration for import-free driver selection."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

from totem_driver_api import DriverManifest

from totem.hardware.catalog.diagnostics import CatalogDiagnostic


_SECRET_FIELDS = ("credential", "secret", "token", "password")
_SECRET_KINDS = {"credential", "file", "inherited_descriptor"}


class ConfigValidationError(ValueError):
    """A configuration value rejects one binding without exposing its value."""

    def __init__(self, diagnostic: CatalogDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.code.replace("_", " "))


@dataclass(frozen=True)
class SecretReference:
    """A credential, path, or inherited descriptor label; never secret material."""

    kind: str
    reference: str

    def __post_init__(self) -> None:
        if self.kind not in _SECRET_KINDS:
            raise ValueError("secret reference kind is not allowed")
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise ValueError("secret reference must be non-empty")

    def to_json_value(self) -> dict[str, str]:
        return {"kind": self.kind, "reference": self.reference}


@dataclass(frozen=True)
class PluginConfig:
    plugin_id: str
    settings: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.plugin_id, "plugin")
        object.__setattr__(self, "settings", _freeze_settings(self.settings))


@dataclass(frozen=True)
class BindingConfig:
    binding_id: str
    plugin_id: str
    settings: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.binding_id, "binding")
        _require_identifier(self.plugin_id, "plugin")
        object.__setattr__(self, "settings", _freeze_settings(self.settings))


@dataclass(frozen=True)
class EffectiveSettings:
    """A validated immutable snapshot passed to one selected binding."""

    values: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _freeze_settings(self.values))

    def to_json_value(self) -> dict[str, object]:
        return _thaw(self.values)

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RuntimeConfig:
    """One controlled-start snapshot with binding > plugin > global precedence."""

    global_settings: Mapping[str, object] = field(default_factory=dict)
    plugins: Tuple[PluginConfig, ...] = ()
    bindings: Tuple[BindingConfig, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_settings", _freeze_settings(self.global_settings))
        if len({item.plugin_id for item in self.plugins}) != len(self.plugins):
            raise ValueError("runtime config has duplicate plugin sections")
        if len({item.binding_id for item in self.bindings}) != len(self.bindings):
            raise ValueError("runtime config has duplicate binding sections")

    @classmethod
    def from_toml_value(cls, value: object) -> "RuntimeConfig":
        if not isinstance(value, Mapping):
            raise ConfigValidationError(_diagnostic("invalid_config", field="document"))
        unknown = set(value).difference({"global", "plugins", "bindings"})
        if unknown:
            raise ConfigValidationError(_diagnostic("unknown_config_section", field=sorted(unknown)[0]))
        global_settings = _settings_mapping(value.get("global", {}), "global")
        raw_plugins = value.get("plugins", {})
        raw_bindings = value.get("bindings", {})
        if not isinstance(raw_plugins, Mapping) or not isinstance(raw_bindings, Mapping):
            raise ConfigValidationError(_diagnostic("invalid_config", field="plugins"))
        plugins = tuple(
            PluginConfig(str(plugin_id), _settings_mapping(settings, str(plugin_id)))
            for plugin_id, settings in sorted(raw_plugins.items())
        )
        bindings = []
        for binding_id, settings in sorted(raw_bindings.items()):
            parsed = _settings_mapping(settings, str(binding_id))
            plugin_id = parsed.pop("plugin", None)
            if not isinstance(plugin_id, str) or not plugin_id.strip():
                raise ConfigValidationError(_diagnostic("missing_binding_plugin", binding_id=str(binding_id), field="plugin"))
            bindings.append(BindingConfig(str(binding_id), plugin_id, parsed))
        return cls(global_settings=global_settings, plugins=plugins, bindings=tuple(bindings))

    def effective_settings(self, manifest: DriverManifest, binding_id: str) -> EffectiveSettings:
        binding = next((item for item in self.bindings if item.binding_id == binding_id), None)
        if binding is not None and binding.plugin_id != manifest.provider_id:
            raise ConfigValidationError(
                _diagnostic("binding_plugin_mismatch", manifest.provider_id, binding_id, "plugin")
            )
        values = dict(manifest.defaults)
        values.update(self.global_settings)
        plugin = next((item for item in self.plugins if item.plugin_id == manifest.provider_id), None)
        if plugin is not None:
            values.update(plugin.settings)
        if binding is not None:
            values.update(binding.settings)
        for field_name, setting in values.items():
            rule = manifest.config_schema.get(field_name)
            if rule is None:
                raise ConfigValidationError(
                    _diagnostic("unknown_config_field", manifest.provider_id, binding_id, field_name)
                )
            _validate_setting(rule, setting, manifest.provider_id, binding_id, field_name)
        return EffectiveSettings(values)

    def execution_mode(self, provider_id: str, binding_id: str, manifest_default: object = "process") -> str:
        """Resolve the explicit host-selection seam without reading provider code.

        Host choice is intentionally a runtime concern, separate from provider
        grouping.  It has the same controlled-start precedence as settings:
        binding, plugin, global, then the manifest default.  Only ``process``
        is implicit; in-process execution must be an explicit accepted value.
        """

        mode = manifest_default
        global_mode = self.global_settings.get("host_mode")
        if global_mode is not None:
            mode = global_mode
        plugin = next((item for item in self.plugins if item.plugin_id == provider_id), None)
        if plugin is not None and "host_mode" in plugin.settings:
            mode = plugin.settings["host_mode"]
        binding = next((item for item in self.bindings if item.binding_id == binding_id), None)
        if binding is not None:
            if binding.plugin_id != provider_id:
                raise ConfigValidationError(_diagnostic("binding_plugin_mismatch", provider_id, binding_id, "plugin"))
            if "host_mode" in binding.settings:
                mode = binding.settings["host_mode"]
        if mode not in {"process", "in_process"}:
            raise ConfigValidationError(_diagnostic("invalid_config_value", provider_id, binding_id, "host_mode"))
        return str(mode)


def toml_loader_for_version(
    version: Tuple[int, int], importer: Callable[[str], object] = importlib.import_module
) -> Callable[[Any], Mapping[str, object]]:
    """Return the one binary TOML loader for the runtime's Python version."""

    module = importer("tomllib" if version >= (3, 11) else "tomli")
    loader = getattr(module, "load", None)
    if not callable(loader):
        raise RuntimeError("TOML module does not expose load")
    return loader


def load_runtime_config(
    path: Path, *, loader: Optional[Callable[[Any], Mapping[str, object]]] = None
) -> RuntimeConfig:
    """Read TOML only in binary mode, then produce an immutable typed snapshot."""

    chosen_loader = loader or toml_loader_for_version(sys.version_info[:2])
    with Path(path).open("rb") as binary_file:
        return RuntimeConfig.from_toml_value(chosen_loader(binary_file))


def _parse_toml_document(value: str) -> Mapping[str, object]:
    """Test-only parser helper; production goes through ``load_runtime_config``."""

    module = importlib.import_module("tomllib" if sys.version_info[:2] >= (3, 11) else "tomli")
    return getattr(module, "loads")(value)


def _settings_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(_diagnostic("invalid_config", field=field))
    return {str(key): _coerce_secret(str(key), item, field) for key, item in value.items()}


def _coerce_secret(field_name: str, value: object, binding_id: str) -> object:
    if isinstance(value, Mapping) and set(value) == {"kind", "reference"}:
        kind = value.get("kind")
        reference = value.get("reference")
        if not isinstance(kind, str) or not isinstance(reference, str):
            raise ConfigValidationError(_diagnostic("invalid_secret_reference", binding_id=binding_id, field=field_name))
        try:
            return SecretReference(kind, reference)
        except ValueError as exc:
            raise ConfigValidationError(_diagnostic("invalid_secret_reference", binding_id=binding_id, field=field_name)) from exc
    if any(token in field_name.lower() for token in _SECRET_FIELDS) and value is not None:
        if not isinstance(value, SecretReference):
            raise ConfigValidationError(_diagnostic("invalid_secret_reference", binding_id=binding_id, field=field_name))
    return value


def _validate_setting(
    rule: Mapping[str, object], value: object, plugin_id: str, binding_id: str, field: str
) -> None:
    kind = rule["type"]
    valid = (
        (kind == "string" and isinstance(value, str))
        or (kind == "integer" and isinstance(value, int) and not isinstance(value, bool))
        or (kind == "boolean" and isinstance(value, bool))
        or (kind == "secret-reference" and isinstance(value, SecretReference))
    )
    if not valid:
        code = "invalid_secret_reference" if kind == "secret-reference" else "invalid_config_value"
        raise ConfigValidationError(_diagnostic(code, plugin_id, binding_id, field))
    allowed = rule.get("enum")
    if allowed is not None and value not in allowed:
        raise ConfigValidationError(_diagnostic("invalid_config_value", plugin_id, binding_id, field))
    minimum = rule.get("minimum")
    if minimum is not None and isinstance(value, int) and value < minimum:
        raise ConfigValidationError(_diagnostic("invalid_config_value", plugin_id, binding_id, field))


def _freeze_settings(value: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("configuration settings must be a mapping")
    return MappingProxyType({str(key): _freeze_value(str(key), item) for key, item in value.items()})


def _freeze_value(field_name: str, value: object) -> object:
    value = _coerce_secret(field_name, value, "")
    if value is None or isinstance(value, (str, int, float, bool, SecretReference)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(str(key), item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_value(field_name, item) for item in value)
    raise ValueError("configuration values must be JSON-compatible or secret references")


def _thaw(value: object) -> object:
    if isinstance(value, SecretReference):
        return value.to_json_value()
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _require_identifier(value: str, kind: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} id must be non-empty".format(kind))


def _diagnostic(
    code: str, plugin_id: str = "", binding_id: str = "", field: str = ""
) -> CatalogDiagnostic:
    return CatalogDiagnostic(code=code, plugin_id=plugin_id, binding_id=binding_id, field=field)
