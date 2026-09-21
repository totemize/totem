"""Static deployed command and unit compatibility contracts."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit


def _unit(name: str) -> str:
    return (ROOT / "deploy" / "systemd" / name).read_text(encoding="utf-8")


def test_package_scripts_and_systemd_service_identities_are_preserved() -> None:
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    api_unit = _unit("totem.service")
    screen_unit = _unit("totem-screen.service")

    assert 'totem = "totem.__main__:main"' in package
    assert 'totem-api = "totem.api.app:start_server"' in package
    assert 'totem-screen = "totem.screen.__main__:main"' in package
    assert "User=totem" in api_unit and "Group=totem" in api_unit
    assert "ExecStart=/opt/totem/.venv/bin/totem --host 0.0.0.0 --port 8000" in api_unit
    assert "--config /etc/totem/hardware.toml" in api_unit
    hardware_template = (
        ROOT / "deploy" / "ansible" / "roles" / "device_manager" / "templates" / "totem-hardware.toml.j2"
    ).read_text(encoding="utf-8")
    assert "[global.hardware_facts]" in hardware_template
    assert "totem_hardware_inventory.facts" in hardware_template
    assert "totem_hardware_inventory.plugins" in hardware_template
    assert '"resource.dbus.org.freedesktop.networkmanager" = "present"' not in hardware_template
    assert "Requires=totem.service" in screen_unit
    assert "After=totem.service" in screen_unit
    assert "Before=fips.service strfry.service totemd.service" in screen_unit
    assert "ExecStart=/opt/totem/.venv/bin/totem-screen run" in screen_unit


def test_hardware_template_omits_absent_resources_from_controlled_inventory() -> None:
    """The deploy template may only serialize facts supplied by preflight."""
    template = (ROOT / "deploy" / "ansible" / "roles" / "device_manager" / "templates" / "totem-hardware.toml.j2").read_text(encoding="utf-8")
    assert "totem_hardware_inventory.facts" in template
    assert "totem_hardware_inventory.plugins" in template
    assert "org.bluez\" = \"present" not in template
    assert "storage-root\" = \"present" not in template


def test_all_deployed_package_entrypoints_resolve_to_callables() -> None:
    for module_name, function_name in (
        ("totem.__main__", "main"),
        ("totem.api.app", "start_server"),
        ("totem.screen.__main__", "main"),
    ):
        assert callable(getattr(import_module(module_name), function_name))


def test_screen_remains_a_bus_client_and_startup_environment_reads_stay_outward() -> None:
    screen_tree = ast.parse((ROOT / "src" / "totem" / "screen" / "__main__.py").read_text(encoding="utf-8"))
    main_source = (ROOT / "src" / "totem" / "__main__.py").read_text(encoding="utf-8")
    api_source = (ROOT / "src" / "totem" / "api" / "app.py").read_text(encoding="utf-8")
    canonical_sources = [
        (ROOT / "src" / "totem" / "hardware" / "api" / "app.py").read_text(encoding="utf-8"),
        (ROOT / "src" / "totem" / "hardware" / "api" / "bus.py").read_text(encoding="utf-8"),
    ]

    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "totem.screen.adapters.hardware_bus"
        for node in ast.walk(screen_tree)
    )
    assert "HardwareBusScreenAdapter(args.device_api_url)" in (ROOT / "src" / "totem" / "screen" / "__main__.py").read_text(encoding="utf-8")
    assert "legacy_runtime_config" in main_source
    assert "from totem.compat.hardware_env import legacy_runtime_config" not in api_source
    assert all("TOTEM_" not in source for source in canonical_sources)
