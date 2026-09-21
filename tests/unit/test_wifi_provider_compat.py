"""Legacy Wi-Fi/support modules remain import-only compatibility facades."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
import warnings

import pytest


ROOT = Path(__file__).parents[2]
LEGACY_TO_CANONICAL = {
    "totem.devices.network.dbus_runtime": "totem.hardware.builtin.radio.dbus_runtime",
    "totem.devices.network.errors": "totem.hardware.builtin.radio.errors",
    "totem.devices.network.models": "totem.hardware.builtin.radio.models",
    "totem.devices.network.nan": "totem.hardware.builtin.radio.nan",
    "totem.devices.network.drivers": "totem.hardware.builtin.radio.drivers",
    "totem.devices.network.drivers.mock_wifi": "totem.hardware.builtin.radio.drivers.mock_wifi",
    "totem.devices.network.drivers.network_manager_wifi": "totem.hardware.builtin.radio.drivers.network_manager_wifi",
    "totem.devices.network.drivers.rpi5_onboard_wifi": "totem.hardware.builtin.radio.drivers.rpi5_onboard_wifi",
    "totem.devices.network.drivers.usb_wifi_adapter": "totem.hardware.builtin.radio.drivers.usb_wifi_adapter",
}


def _module_path(module_name: str) -> Path:
    module_path = ROOT / "src" / Path(*module_name.split(".")).with_suffix(".py")
    return module_path if module_path.exists() else module_path.with_suffix("") / "__init__.py"


def _public_names(module: object) -> set[str]:
    return {name for name in vars(module) if not name.startswith("_")}


def _load_legacy_facade(module_name: str) -> object:
    """Execute the direct facade after sibling module imports touched its parent.

    Python binds a directly imported child module onto its legacy parent package.
    Reloading the one-line facade restores its declared canonical re-exports so
    each inventory row checks the source contract rather than another test's
    package-attribute side effect.
    """

    return importlib.reload(importlib.import_module(module_name))


@pytest.mark.unit
@pytest.mark.parametrize("legacy_name,canonical_name", LEGACY_TO_CANONICAL.items())
def test_wifi_legacy_modules_are_exhaustive_direct_reexports(
    legacy_name: str, canonical_name: str
) -> None:
    """Every legacy path exposes the exact canonical objects and signatures."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        legacy = _load_legacy_facade(legacy_name)
    canonical = importlib.import_module(canonical_name)

    assert _public_names(legacy) == _public_names(canonical)
    for name in _public_names(canonical):
        legacy_value = getattr(legacy, name)
        canonical_value = getattr(canonical, name)
        assert legacy_value is canonical_value
        if callable(canonical_value):
            try:
                canonical_signature = inspect.signature(canonical_value)
            except (TypeError, ValueError):
                continue
            assert inspect.signature(legacy_value) == canonical_signature


@pytest.mark.unit
@pytest.mark.parametrize("legacy_name,canonical_name", LEGACY_TO_CANONICAL.items())
def test_wifi_legacy_module_bodies_only_import_the_canonical_module(
    legacy_name: str, canonical_name: str
) -> None:
    """Facades cannot recreate D-Bus, provider, selection, or session ownership."""
    body = ast.parse(_module_path(legacy_name).read_text(encoding="utf-8")).body

    assert len(body) == 1
    statement = body[0]
    assert isinstance(statement, ast.ImportFrom)
    assert statement.level == 0
    assert statement.module == canonical_name
    assert [(name.name, name.asname) for name in statement.names] == [("*", None)]
