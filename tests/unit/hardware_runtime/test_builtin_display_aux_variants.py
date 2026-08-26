"""Exhaustive mock-only inventory for provider-owned auxiliary display modules."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

from totem.hardware.catalog.metadata import CatalogScanner


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


AUXILIARY_DRIVER_MODULES = frozenset(
    (
        "mock_eink",
        "waveshare_3in7",
        "waveshare_3in7_pi5",
    )
)
AUXILIARY_VENDOR_MODULES = frozenset(("epd3in7", "epdconfig"))
AUXILIARY_VENDOR_FILES = frozenset(("__init__.py", "epd3in7.py", "epdconfig.py"))


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-display"
    value = "totem.hardware.builtin.display.provider:create_provider"


class _DisplayDistribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)

    def __init__(self) -> None:
        self.files = (Path("totem/hardware/builtin/display/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/display/totem-driver-manifest.json"
        return (
            Path(__file__).parents[3]
            / "src"
            / "totem"
            / "hardware"
            / "builtin"
            / "display"
            / "totem-driver-manifest.json"
        )


def _provider_auxiliary_driver_names() -> set[str]:
    package = importlib.import_module("totem.hardware.builtin.display.drivers")
    return {
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.name == "mock_eink" or module.name.startswith("waveshare_3in7")
    }


def _provider_vendor_module_names() -> set[str]:
    directory = _vendor_directory()
    return {module.name for module in pkgutil.iter_modules((str(directory),))}


def _vendor_directory() -> Path:
    return (
        Path(__file__).parents[3]
        / "src"
        / "totem"
        / "hardware"
        / "builtin"
        / "display"
        / "waveshare_epd"
    )


def test_provider_owns_an_exhaustive_auxiliary_variant_inventory() -> None:
    assert _provider_auxiliary_driver_names() == AUXILIARY_DRIVER_MODULES
    assert _provider_vendor_module_names() == AUXILIARY_VENDOR_MODULES
    assert {path.name for path in _vendor_directory().glob("*.py")} == AUXILIARY_VENDOR_FILES


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
    module_path = _vendor_directory() / "{0}.py".format(module_name)

    assert "totem.devices" not in module_path.read_text(encoding="utf-8")


def test_catalog_does_not_import_the_provider_or_vendor_support() -> None:
    module_names = (
        "totem.hardware.builtin.display.provider",
        "totem.hardware.builtin.display.waveshare_epd",
        "totem.hardware.builtin.display.waveshare_epd.epd3in7",
        "totem.hardware.builtin.display.waveshare_epd.epdconfig",
    )
    for module_name in module_names:
        sys.modules.pop(module_name, None)

    catalog = CatalogScanner(distributions=lambda: (_DisplayDistribution(),)).snapshot()

    assert catalog.diagnostics == ()
    assert not any(module_name in sys.modules for module_name in module_names)


def test_mock_driver_requires_explicit_selection_and_keeps_bytes_in_memory() -> None:
    module = importlib.import_module("totem.hardware.builtin.display.drivers.mock_eink")
    driver = module.Driver()

    assert driver.IS_MOCK is True
    with pytest.raises(RuntimeError, match="not initialized"):
        driver.display_bytes(b"frame")

    assert driver.init() is True
    driver.display_bytes(bytearray(b"frame"))

    assert driver.last_image == b"frame"


def test_mock_driver_is_not_a_provider_fallback() -> None:
    manifest_path = (
        Path(__file__).parents[3]
        / "src"
        / "totem"
        / "hardware"
        / "builtin"
        / "display"
        / "totem-driver-manifest.json"
    )

    assert "mock_eink" not in manifest_path.read_text(encoding="utf-8")


def test_3in7_legacy_mock_mode_keeps_vendor_support_unloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("totem.hardware.builtin.display.drivers.waveshare_3in7")
    monkeypatch.setattr(module.WaveshareEPD3in7, "_detect_hardware", lambda _self: "mock")
    driver = module.WaveshareEPD3in7(mock_mode=True)

    assert driver.width == 280 and driver.height == 480
    assert driver.epd is None
    assert driver.init() is None
    assert driver.initialized is True
    assert len(driver.getbuffer(object())) == 16_800
    assert len(driver.getbuffer_4Gray(object())) == 33_600
