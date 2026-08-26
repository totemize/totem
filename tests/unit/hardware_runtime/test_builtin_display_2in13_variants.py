"""Exhaustive mock-only inventory for provider-owned Waveshare 2.13 panels."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Iterable, Iterator, List, Tuple

import pytest
from PIL import Image


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


@dataclass
class RecordingSpi:
    opened: List[Tuple[int, int]] = field(default_factory=list)
    writes: List[List[int]] = field(default_factory=list)

    def open(self, bus: int, device: int) -> None:
        self.opened.append((bus, device))

    def writebytes(self, values: Iterable[int]) -> None:
        self.writes.append(list(values))

    def writebytes2(self, values: Iterable[int]) -> None:
        self.writebytes(values)

    def close(self) -> None:
        return None


class RecordingGpio:
    BCM, OUT, IN, HIGH, LOW, PUD_DOWN = 0, 2, 3, 1, 0, 21

    def __init__(self) -> None:
        self.outputs: List[Tuple[int, int]] = []

    def setwarnings(self, enabled: bool) -> None:
        del enabled

    def setmode(self, mode: int) -> None:
        del mode

    def setup(self, pin: int, mode: int, **kwargs: object) -> None:
        del pin, mode, kwargs

    def output(self, pin: int, value: int) -> None:
        self.outputs.append((pin, value))

    def input(self, pin: int) -> int:
        del pin
        return self.LOW

    def cleanup(self, pin: int = 0) -> None:
        del pin


VARIANTS = (
    ("waveshare_2in13", "spi-gpio", 0),
    ("waveshare_2in13_pi5", "pi5-hardware-cs", 3_984),
    ("waveshare_2in13_pi5_sw_cs", "pi5-software-cs", 3_984),
    ("waveshare_2in13_v1", "spi-gpio", 3_984),
    ("waveshare_2in13_v2", "spi-gpio", 0),
    ("waveshare_2in13_v3", "spi-gpio", 3_984),
    ("waveshare_2in13_v4", "spi-gpio", 3_984),
)


_MISSING = object()


@contextmanager
def _fresh_variant_import(qualified_name: str) -> Iterator[ModuleType]:
    """Import one provider module afresh without leaking its new class objects.

    Compatibility facades intentionally retain direct aliases to canonical
    classes.  A test-only ``sys.modules.pop()`` therefore must restore both the
    module cache and its parent-package attribute; otherwise a later import can
    create a second ``Driver`` class with the same qualified name.
    """

    parent_name, _, module_name = qualified_name.rpartition(".")
    parent = importlib.import_module(parent_name)
    previous_module = sys.modules.get(qualified_name, _MISSING)
    previous_attribute = getattr(parent, module_name, _MISSING)

    try:
        sys.modules.pop(qualified_name, None)
        yield importlib.import_module(qualified_name)
    finally:
        if previous_module is _MISSING:
            sys.modules.pop(qualified_name, None)
        else:
            sys.modules[qualified_name] = previous_module

        if previous_attribute is _MISSING:
            delattr(parent, module_name)
        else:
            setattr(parent, module_name, previous_attribute)


def _provider_variant_names() -> set[str]:
    package = importlib.import_module("totem.hardware.builtin.display.drivers")
    return {
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.name.startswith("waveshare_2in13")
    }


def test_provider_owns_an_exhaustive_2in13_variant_inventory() -> None:
    assert _provider_variant_names() == {name for name, _transport, _offset in VARIANTS}


@pytest.mark.parametrize("module_name, _transport_kind, _offset", VARIANTS)
def test_variant_imports_do_not_load_hardware_libraries_or_legacy_owner(
    module_name: str, _transport_kind: str, _offset: int
) -> None:
    qualified_name = "totem.hardware.builtin.display.drivers.{0}".format(module_name)
    hardware_modules = ("spidev", "gpiod", "RPi.GPIO")
    before = {name for name in hardware_modules if name in sys.modules}

    with _fresh_variant_import(qualified_name) as module:
        assert {name for name in hardware_modules if name in sys.modules} == before
        assert "totem.devices" not in Path(module.__file__).read_text(encoding="utf-8")


def test_fresh_import_probe_preserves_legacy_driver_identity() -> None:
    legacy = importlib.import_module(
        "totem.devices.display.drivers.waveshare_2in13"
    )
    canonical = importlib.import_module(
        "totem.hardware.builtin.display.drivers.waveshare_2in13_v2"
    )

    with _fresh_variant_import(
        "totem.hardware.builtin.display.drivers.waveshare_2in13_v2"
    ):
        pass

    assert legacy.Driver is canonical.Driver


@pytest.mark.parametrize("module_name, transport_kind, black_pixel_offset", VARIANTS)
def test_variant_contract_uses_only_injected_mock_transports(
    module_name: str, transport_kind: str, black_pixel_offset: int
) -> None:
    module = importlib.import_module(
        "totem.hardware.builtin.display.drivers.{0}".format(module_name)
    )
    spi, gpio = RecordingSpi(), RecordingGpio()
    panel = module.Driver(spi=spi, gpio=gpio, sleep=lambda _seconds: None)

    assert panel.width == 250 and panel.height == 122
    assert panel.MOUNT_ROTATION_DEGREES == 180
    assert panel.TRANSPORT_KIND == transport_kind
    assert spi.opened == []
    assert spi.writes == []
    assert gpio.outputs == []

    image = Image.new("1", (250, 122), 1)
    image.putpixel((0, 0), 0)
    frame = panel.getbuffer(image)
    assert len(frame) == panel.FRAME_BYTES == 4_000
    assert frame[black_pixel_offset] == 0x7F

    panel.init()
    assert spi.opened == [(0, 0)]
    assert spi.writes


def test_software_chip_select_wraps_each_spi_transfer() -> None:
    module = importlib.import_module(
        "totem.hardware.builtin.display.drivers.waveshare_2in13_pi5_sw_cs"
    )
    spi, gpio = RecordingSpi(), RecordingGpio()
    panel = module.Driver(spi=spi, gpio=gpio, sleep=lambda _seconds: None)

    panel.send_command(0x12)

    assert gpio.outputs == [(panel.cs_pin, gpio.LOW), (panel.dc_pin, gpio.LOW), (panel.cs_pin, gpio.HIGH)]
    assert spi.writes == [[0x12]]
