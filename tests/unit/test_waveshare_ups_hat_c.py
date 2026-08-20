"""Waveshare UPS HAT (C) driver tests."""

import pytest

from totem.devices.contracts import DriverState
from totem.devices.ups.drivers.waveshare_ups_hat_c import Driver
from totem.devices.ups.ups import UPS_DRIVERS


pytestmark = pytest.mark.unit


class FakeSMBus:
    def __init__(self, registers):
        self.registers = registers
        self.reads = []
        self.writes = []
        self.closed = False

    def read_i2c_block_data(self, address, register, length):
        self.reads.append((address, register, length))
        return self.registers[register]

    def write_i2c_block_data(self, address, register, data):
        self.writes.append((address, register, list(data)))

    def close(self):
        self.closed = True


def _driver(registers):
    bus = FakeSMBus(registers)
    driver = Driver(bus_factory=lambda bus_number: bus)
    return driver, bus


def test_waveshare_driver_is_registered():
    driver = UPS_DRIVERS.load("waveshare-ups-hat-c")

    assert isinstance(driver, Driver)


def test_waveshare_reads_voltage_percentage_and_signed_current():
    driver, bus = _driver(
        {
            0x02: [0x1C, 0x20],  # 3.6 V
            0x04: [0xF9, 0x98],  # approximately -0.25 A
        }
    )

    assert driver.init() is True
    status = driver.get_status()

    assert status.model == "Waveshare UPS HAT (C)"
    assert status.voltage_volts == pytest.approx(3.6)
    assert status.battery_percent == pytest.approx(50.0)
    assert status.current_amps == pytest.approx(-0.25, abs=0.001)
    assert status.power_plugged is None
    assert (Driver.ADDRESS, 0x05, [0x68, 0xF4]) in bus.writes
    assert (Driver.ADDRESS, 0x00, [0x0E, 0xEF]) in bus.writes


@pytest.mark.parametrize(
    ("voltage_register", "expected_percent"),
    (
        ([0x17, 0x70], 0.0),  # 3.0 V
        ([0x20, 0xD0], 100.0),  # 4.2 V
    ),
)
def test_waveshare_clamps_battery_percentage(voltage_register, expected_percent):
    driver, _ = _driver(
        {
            0x02: voltage_register,
            0x04: [0x00, 0x00],
        }
    )

    driver.init()

    assert driver.get_status().battery_percent == expected_percent


def test_waveshare_rejects_implausible_probe_and_closes_bus():
    driver, bus = _driver({0x02: [0x00, 0x00]})

    with pytest.raises(RuntimeError, match="implausible battery voltage"):
        driver.init()

    assert bus.closed is True
    assert driver.health().state == DriverState.CLOSED


def test_waveshare_close_releases_bus():
    driver, bus = _driver({0x02: [0x1C, 0x20]})

    driver.init()
    driver.close()

    assert bus.closed is True
    assert driver.health().state == DriverState.CLOSED
