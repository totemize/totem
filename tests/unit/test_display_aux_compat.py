"""Compatibility-only inventory for historical auxiliary display paths."""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


LEGACY_DRIVERS = "totem.devices.display.drivers"
CANONICAL_DRIVERS = "totem.hardware.builtin.display.drivers"
LEGACY_VENDOR = "totem.devices.display.waveshare_epd"
CANONICAL_VENDOR = "totem.hardware.builtin.display.waveshare_epd"

# Keep this inventory exhaustive: each historical auxiliary module needs an
# explicit canonical target before the legacy namespace can expose it.
COMPATIBILITY_PAIRS = (
    ("mock_eink", LEGACY_DRIVERS, CANONICAL_DRIVERS),
    ("waveshare_3in7", LEGACY_DRIVERS, CANONICAL_DRIVERS),
    ("waveshare_3in7_pi5", LEGACY_DRIVERS, CANONICAL_DRIVERS),
    ("__init__", LEGACY_VENDOR, CANONICAL_VENDOR),
    ("epd3in7", LEGACY_VENDOR, CANONICAL_VENDOR),
    ("epdconfig", LEGACY_VENDOR, CANONICAL_VENDOR),
)


def _module_names(package_name: str, expected: set[str]) -> set[str]:
    package = importlib.import_module(package_name)
    discovered = {module.name for module in pkgutil.iter_modules(package.__path__)}
    return discovered & expected


def _public_names(module: object) -> set[str]:
    return {name for name in vars(module) if not name.startswith("_")}


def _compatibility_nodes(path: Path) -> list[ast.stmt]:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body


def _is_compatibility_node(node: ast.stmt, canonical_package: str) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return isinstance(node.value.value, str)
    if isinstance(node, ast.ImportFrom):
        return node.module is not None and node.module.startswith(canonical_package)
    if isinstance(node, ast.Assign):
        return all(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    return False


def _module_name(package_name: str, module_name: str) -> str:
    return package_name if module_name == "__init__" else "{}.{}".format(package_name, module_name)


def test_legacy_inventory_is_exactly_the_explicit_compatibility_table() -> None:
    driver_expected = {
        legacy_name
        for legacy_name, legacy_package, _canonical_package in COMPATIBILITY_PAIRS
        if legacy_package == LEGACY_DRIVERS
    }
    vendor_expected = {
        legacy_name
        for legacy_name, legacy_package, _canonical_package in COMPATIBILITY_PAIRS
        if legacy_package == LEGACY_VENDOR and legacy_name != "__init__"
    }

    assert _module_names(LEGACY_DRIVERS, driver_expected) == driver_expected
    assert _module_names(CANONICAL_DRIVERS, driver_expected) == driver_expected
    assert _module_names(LEGACY_VENDOR, vendor_expected) == vendor_expected
    assert _module_names(CANONICAL_VENDOR, vendor_expected) == vendor_expected


@pytest.mark.parametrize("legacy_name, legacy_package, canonical_package", COMPATIBILITY_PAIRS)
def test_legacy_imports_reexport_every_canonical_public_name_with_identity_and_signature(
    legacy_name: str, legacy_package: str, canonical_package: str
) -> None:
    legacy = importlib.import_module(_module_name(legacy_package, legacy_name))
    canonical = importlib.import_module(_module_name(canonical_package, legacy_name))

    assert _public_names(legacy) == _public_names(canonical)
    for name in _public_names(canonical):
        legacy_value = getattr(legacy, name)
        canonical_value = getattr(canonical, name)
        assert legacy_value is canonical_value
        if inspect.isclass(canonical_value) or inspect.isroutine(canonical_value):
            assert inspect.signature(legacy_value) == inspect.signature(canonical_value)


@pytest.mark.parametrize("legacy_name, legacy_package, canonical_package", COMPATIBILITY_PAIRS)
def test_legacy_modules_contain_only_canonical_reexports(
    legacy_name: str, legacy_package: str, canonical_package: str
) -> None:
    legacy = importlib.import_module(_module_name(legacy_package, legacy_name))
    nodes = _compatibility_nodes(Path(legacy.__file__))

    assert nodes
    assert all(_is_compatibility_node(node, canonical_package) for node in nodes)
    assert any(isinstance(node, ast.ImportFrom) for node in nodes)
