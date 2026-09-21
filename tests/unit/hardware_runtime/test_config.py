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
    assert RuntimeConfig().effective_settings(_manifest(), "display.none").to_json_value() == {
        "host_mode": "process",
        "timeout": 5,
    }
    assert RuntimeConfig(
        plugins=(PluginConfig("fixture.display", {"timeout": 20}),)
    ).effective_settings(_manifest(), "display.none").to_json_value()["timeout"] == 20
    assert RuntimeConfig(
        global_settings={"timeout": 10}
    ).effective_settings(_manifest(), "display.none").to_json_value()["timeout"] == 10


def test_runtime_only_composition_fields_do_not_leak_into_provider_settings() -> None:
    effective = RuntimeConfig(
        global_settings={
            "hardware_facts": {"resource.spi": "spi0.0"},
            "no_hardware": False,
            "timeout": 10,
        }
    ).effective_settings(_manifest(), "display.none")

    assert effective.to_json_value() == {"host_mode": "process", "timeout": 10}


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

    tomli_loader = config.toml_loader_for_version((3, 9), importer)
    assert tomli_loader is not None
    loaded = load_runtime_config(config_path, loader=tomli_loader)
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


def test_concurrent_config_readers_share_valid_snapshot_and_stable_sibling_rejection() -> None:
    runtime = RuntimeConfig(
        bindings=(
            BindingConfig("display.good", "fixture.display", {"timeout": 8}),
            BindingConfig("display.bad", "fixture.display", {"unknown": "ignored"}),
        )
    )

    def read_good(_item: int) -> str:
        return runtime.effective_settings(_manifest(), "display.good").to_json()

    def reject_bad(_item: int) -> str:
        with pytest.raises(ConfigValidationError) as raised:
            runtime.effective_settings(_manifest(), "display.bad")
        return raised.value.diagnostic.to_json()

    with ThreadPoolExecutor(max_workers=8) as executor:
        good_values = list(executor.map(read_good, range(32)))
        bad_diagnostics = list(executor.map(reject_bad, range(32)))

    assert len(set(good_values)) == 1
    assert len(set(bad_diagnostics)) == 1
