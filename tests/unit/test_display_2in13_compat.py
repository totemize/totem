"""Compatibility-only inventory for every historical Waveshare 2.13 path."""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


LEGACY_PACKAGE = "totem.devices.display.drivers"
CANONICAL_PACKAGE = "totem.hardware.builtin.display.drivers"

# Keep this table complete: a new legacy 2.13 module must have an explicit
# canonical target before compatibility can be claimed.
COMPATIBILITY_PAIRS = (
    ("_waveshare_2in13_base", "_waveshare_2in13_base", "Waveshare2in13Base"),
    ("waveshare_2in13", "waveshare_2in13", "Driver"),
    ("waveshare_2in13_pi5", "waveshare_2in13_pi5", "Driver"),
    ("waveshare_2in13_pi5_sw_cs", "waveshare_2in13_pi5_sw_cs", "Driver"),
    ("waveshare_2in13_v1", "waveshare_2in13_v1", "Driver"),
    ("waveshare_2in13_v2", "waveshare_2in13_v2", "Driver"),
    ("waveshare_2in13_v3", "waveshare_2in13_v3", "Driver"),
    ("waveshare_2in13_v4", "waveshare_2in13_v4", "Driver"),
)


def _module_names(package_name: str) -> set[str]:
    package = importlib.import_module(package_name)
    return {
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.name == "_waveshare_2in13_base"
        or module.name.startswith("waveshare_2in13")
    }


def _compatibility_nodes(path: Path) -> list[ast.stmt]:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path)).body


def _is_compatibility_node(node: ast.stmt) -> bool:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return isinstance(node.value.value, str)
    if isinstance(node, ast.ImportFrom):
        return node.module is not None and node.module.startswith(CANONICAL_PACKAGE)
    if isinstance(node, ast.Assign):
        return all(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    return False


def test_legacy_inventory_is_exactly_the_explicit_compatibility_table() -> None:
    expected = {legacy for legacy, _canonical, _symbol in COMPATIBILITY_PAIRS}

    assert _module_names(LEGACY_PACKAGE) == expected
    assert _module_names(CANONICAL_PACKAGE) == expected


@pytest.mark.parametrize("legacy_name, canonical_name, symbol", COMPATIBILITY_PAIRS)
def test_legacy_imports_reexport_the_canonical_class_with_its_signature(
    legacy_name: str, canonical_name: str, symbol: str
) -> None:
    legacy = importlib.import_module("{0}.{1}".format(LEGACY_PACKAGE, legacy_name))
    canonical = importlib.import_module(
        "{0}.{1}".format(CANONICAL_PACKAGE, canonical_name)
    )

    assert getattr(legacy, symbol) is getattr(canonical, symbol)
    assert inspect.signature(getattr(legacy, symbol)) == inspect.signature(
        getattr(canonical, symbol)
    )


@pytest.mark.parametrize("legacy_name, _canonical_name, _symbol", COMPATIBILITY_PAIRS)
def test_legacy_modules_contain_only_canonical_reexports(
    legacy_name: str, _canonical_name: str, _symbol: str
) -> None:
    module = importlib.import_module("{0}.{1}".format(LEGACY_PACKAGE, legacy_name))
    nodes = _compatibility_nodes(Path(module.__file__))

    assert nodes
    assert all(_is_compatibility_node(node) for node in nodes)
    assert any(isinstance(node, ast.ImportFrom) for node in nodes)
