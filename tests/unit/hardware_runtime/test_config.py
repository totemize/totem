"""Typed startup configuration and secret-reference boundary tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from totem.hardware.runtime import config
from totem.hardware.runtime.config import (
    BindingConfig,
    ConfigValidationError,
    PluginConfig,
    RuntimeConfig,
    SecretReference,
    load_runtime_config,
)
from totem_driver_api import DriverManifest


pytestmark = pytest.mark.unit


def _manifest() -> DriverManifest:
    return DriverManifest.from_json(
        {
            "manifest_major": 1,
            "api_major": 1,
            "provider_id": "fixture.display",
            "provider_version": "1.0.0",
            "capabilities": ["display.frame-sink@1"],
            "predicates": [{"fact": "resource.spi", "equals": "spi0.0"}],
            "prerequisites": ["linux"],
            "config_schema": {
                "host_mode": {"type": "string", "enum": ["process", "in_process"]},
                "timeout": {"type": "integer", "minimum": 1},
                "credential": {"type": "secret-reference"},
            },
            "defaults": {"host_mode": "process", "timeout": 5},
            "resources": [
                {
                    "kind": "spi",
                    "identifier": "spi0.0",
                    "exclusive": True,
                    "group": "display",
                }
            ],
            "privileges": ["device:spi"],
            "grouping": "provider",
            "factory": "totem_driver_fixture.provider:create_provider",
        }
    )


def test_binding_plugin_global_and_manifest_defaults_have_exact_precedence() -> None:
    runtime = RuntimeConfig(
        global_settings={"host_mode": "process", "timeout": 10},
        plugins=(PluginConfig("fixture.display", {"timeout": 20}),),
        bindings=(BindingConfig("display.main", "fixture.display", {"timeout": 30}),),
    )

    effective = runtime.effective_settings(_manifest(), "display.main")

    assert effective.to_json_value() == {"host_mode": "process", "timeout": 30}


def test_invalid_sibling_binding_is_isolated_and_diagnostics_redact_secret_values() -> None:
    secret_value = "do-not-leak-this-credential"
    runtime = RuntimeConfig(
        bindings=(
            BindingConfig("display.good", "fixture.display", {"timeout": 9}),
            BindingConfig("display.bad", "fixture.display", {"unknown": secret_value}),
        )
    )

    assert runtime.effective_settings(_manifest(), "display.good").to_json_value() == {
        "host_mode": "process",
        "timeout": 9,
    }
    with pytest.raises(ConfigValidationError) as raised:
        runtime.effective_settings(_manifest(), "display.bad")

    diagnostic = raised.value.diagnostic
    assert diagnostic.code == "unknown_config_field"
    assert diagnostic.plugin_id == "fixture.display"
    assert diagnostic.binding_id == "display.bad"
    assert diagnostic.field == "unknown"
    assert secret_value not in str(diagnostic)
    assert secret_value not in diagnostic.to_json()


def test_toml_loader_uses_binary_parser_seam_for_tomli_and_tomllib(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.toml"
    config_path.write_text(
        """
[global]
host_mode = "process"
[plugins."fixture.display"]
timeout = 20
[bindings."display.main"]
plugin = "fixture.display"
timeout = 30
credential = { kind = "credential", reference = "systemd:display" }
""".strip(),
        encoding="utf-8",
    )
    imported = []

    class _Parser:
        def load(self, binary_file):
            assert "b" in binary_file.mode
            return config._parse_toml_document(binary_file.read().decode("utf-8"))

    def importer(name: str):
        imported.append(name)
        return _Parser()

    assert config.toml_loader_for_version((3, 9), importer) is not None
    loaded = load_runtime_config(config_path, loader=config.toml_loader_for_version((3, 9), importer))
    assert imported == ["tomli"]
    assert loaded.effective_settings(_manifest(), "display.main").to_json_value() == {
        "credential": {"kind": "credential", "reference": "systemd:display"},
        "host_mode": "process",
        "timeout": 30,
    }
    assert config.toml_loader_for_version((3, 11), importer) is not None
    assert imported[-1] == "tomllib"


def test_secret_references_are_only_descriptors_and_snapshots_are_immutable() -> None:
    reference = SecretReference("inherited_descriptor", "fd:7")
    runtime = RuntimeConfig(
        bindings=(
            BindingConfig("display.main", "fixture.display", {"credential": reference}),
        )
    )
    settings = runtime.effective_settings(_manifest(), "display.main")

    assert settings.to_json_value()["credential"] == {
        "kind": "inherited_descriptor",
        "reference": "fd:7",
    }
    with pytest.raises(TypeError):
        settings.values["timeout"] = 1  # type: ignore[index]
    with ThreadPoolExecutor(max_workers=8) as executor:
        rendered = list(executor.map(lambda _item: settings.to_json(), range(32)))
    assert len(set(rendered)) == 1
    with pytest.raises(ConfigValidationError, match="secret reference"):
        RuntimeConfig.from_toml_value(
            {"bindings": {"display.main": {"plugin": "fixture.display", "credential": "raw"}}}
        )
