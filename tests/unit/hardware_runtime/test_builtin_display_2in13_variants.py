"""Exhaustive mock-only inventory for provider-owned Waveshare 2.13 panels."""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

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
    ("waveshare_2in13", "spi-gpio"),
    ("waveshare_2in13_pi5", "pi5-hardware-cs"),
    ("waveshare_2in13_pi5_sw_cs", "pi5-software-cs"),
    ("waveshare_2in13_v1", "spi-gpio"),
    ("waveshare_2in13_v2", "spi-gpio"),
    ("waveshare_2in13_v3", "spi-gpio"),
    ("waveshare_2in13_v4", "spi-gpio"),
)


def _provider_variant_names() -> set[str]:
    package = importlib.import_module("totem.hardware.builtin.display.drivers")
    return {
        module.name
        for module in pkgutil.iter_modules(package.__path__)
        if module.name.startswith("waveshare_2in13")
    }


def test_provider_owns_an_exhaustive_2in13_variant_inventory() -> None:
    assert _provider_variant_names() == {name for name, _transport in VARIANTS}


@pytest.mark.parametrize("module_name, transport_kind", VARIANTS)
def test_variant_contract_uses_only_injected_mock_transports(
    module_name: str, transport_kind: str
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

    frame = panel.getbuffer(Image.new("1", (250, 122), 1))
    assert len(frame) == panel.FRAME_BYTES == 4_000

    panel.init()
    assert spi.opened == [(0, 0)]
    assert spi.writes
