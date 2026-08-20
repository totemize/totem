"""PiSugar2 UPS primitive and driver tests."""

from pathlib import Path

import pytest

from totem.devices.contracts import DriverState
from totem.devices.ups.drivers.pisugar2 import Driver
from totem.devices.ups.ups import UPS


pytestmark = pytest.mark.unit


class FakeSMBus:
    def __init__(self, registers):
        self.registers = registers
        self.reads = []
        self.closed = False

    def read_byte_data(self, address, register):
        self.reads.append((address, register))
        return self.registers[register]

    def close(self):
        self.closed = True


def _driver(registers):
    bus = FakeSMBus(registers)
    driver = Driver(bus_factory=lambda bus_number: bus)
    return driver, bus


def test_pisugar2_reads_status_without_writing_registers():
    driver, bus = _driver(
        {
            0xA2: 0x5D,
            0xA3: 0x14,  # approximately 4.0 V
            0xA4: 0x9E,
            0xA5: 0x02,  # approximately +0.5 A
            0x55: 0x10,
        }
    )

    assert driver.init() is True
    status = driver.get_status()

    assert status.model == "PiSugar 2"
    assert status.voltage_volts == pytest.approx(4.0, abs=0.001)
    assert status.battery_percent == pytest.approx(80.0, abs=0.2)
    assert status.current_amps == pytest.approx(0.5, abs=0.001)
    assert status.power_plugged is True
    assert set(bus.reads) == {
        (Driver.ADDRESS, 0xA2),
        (Driver.ADDRESS, 0xA3),
        (Driver.ADDRESS, 0xA4),
        (Driver.ADDRESS, 0xA5),
        (Driver.ADDRESS, 0x55),
    }


def test_pisugar2_decodes_signed_current_and_closes_bus():
    driver, bus = _driver(
        {
            0xA2: 0x5D,
            0xA3: 0x14,
            0xA4: 0xB1,
            0xA5: 0x3E,  # approximately -0.25 A
            0x55: 0x00,
        }
    )

    driver.init()
    assert driver.get_status().current_amps == pytest.approx(-0.25, abs=0.001)
    driver.close()

    assert bus.closed is True
    assert driver.health().state == DriverState.CLOSED


def test_pisugar2_rejects_implausible_probe_and_closes_bus():
    driver, bus = _driver({0xA2: 0x00, 0xA3: 0x00})

    with pytest.raises(RuntimeError, match="implausible battery voltage"):
        driver.init()

    assert bus.closed is True
    assert not driver.initialized


def test_ups_auto_detection_uses_configured_i2c_bus(monkeypatch):
    monkeypatch.setenv("TOTEM_I2C_BUS", "7")
    monkeypatch.setattr(
        Path,
        "exists",
        lambda path: str(path) == "/dev/i2c-7",
    )

    assert UPS._detect_hardware() == "pisugar2"
