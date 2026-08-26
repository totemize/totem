"""Exhaustive mock-only inventory for provider-owned auxiliary display modules."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


AUXILIARY_DRIVER_MODULES = frozenset(
    (
        "mock_eink",
        "waveshare_3in7",
        "waveshare_3in7_pi5",
    )
)
AUXILIARY_VENDOR_MODULES = frozenset(("epd3in7", "epdconfig"))


def _provider_auxiliary_driver_names() -> set[str]:
    package = importlib.import_module("totem.hardware.builtin.display.drivers")
    return {
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.name == "mock_eink" or module.name.startswith("waveshare_3in7")
    }


def _provider_vendor_module_names() -> set[str]:
    package = importlib.import_module("totem.hardware.builtin.display.waveshare_epd")
    return {module.name for module in pkgutil.iter_modules(package.__path__)}


def test_provider_owns_an_exhaustive_auxiliary_variant_inventory() -> None:
    assert _provider_auxiliary_driver_names() == AUXILIARY_DRIVER_MODULES
    assert _provider_vendor_module_names() == AUXILIARY_VENDOR_MODULES


@pytest.mark.parametrize("module_name", sorted(AUXILIARY_DRIVER_MODULES))
def test_auxiliary_driver_imports_stay_inside_the_provider_child(
    module_name: str,
) -> None:
    qualified_name = "totem.hardware.builtin.display.drivers.{0}".format(module_name)
    sys.modules.pop(qualified_name, None)

    module = importlib.import_module(qualified_name)

    assert "totem.devices" not in Path(module.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("module_name", sorted(AUXILIARY_VENDOR_MODULES))
def test_vendor_support_modules_are_provider_owned(module_name: str) -> None:
    module = importlib.import_module(
        "totem.hardware.builtin.display.waveshare_epd.{0}".format(module_name)
    )

    assert "totem.devices" not in Path(module.__file__).read_text(encoding="utf-8")


def test_mock_driver_requires_explicit_selection_and_keeps_bytes_in_memory() -> None:
    module = importlib.import_module("totem.hardware.builtin.display.drivers.mock_eink")
    driver = module.Driver()

    assert driver.IS_MOCK is True
    with pytest.raises(RuntimeError, match="not initialized"):
        driver.display_bytes(b"frame")

    assert driver.init() is True
    driver.display_bytes(bytearray(b"frame"))

    assert driver.last_image == b"frame"
