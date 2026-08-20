"""Waveshare UPS HAT (C) telemetry through its INA219 monitor."""

import os
from typing import Callable, Optional

from totem.devices.ups.ups import UPSDeviceInterface, UPSStatus


class Driver(UPSDeviceInterface):
    """Read battery telemetry from the UPS HAT (C) at I2C address 0x43.

    Initialization writes only the INA219 calibration and measurement config
    required for current readings. It never writes to the HAT's ETA6003
    charger, TPS61088 boost converter, or battery protection circuitry.
    """

    ADDRESS = 0x43
    MODEL = "Waveshare UPS HAT (C)"

    _REG_CONFIG = 0x00
    _REG_BUS_VOLTAGE = 0x02
    _REG_CURRENT = 0x04
    _REG_CALIBRATION = 0x05

    # Values used by Waveshare's reference INA219.py for the HAT's 0.01-ohm
    # shunt: 16 V range, /2 gain, 12-bit 32-sample ADCs, continuous mode.
    _CALIBRATION = 26868
    _CONFIG = 0x0EEF
    _CURRENT_LSB_MILLIAMPS = 0.1524

    def __init__(
        self,
        bus_number: Optional[int] = None,
        *,
        bus_factory: Optional[Callable[[int], object]] = None,
    ):
        configured_bus = os.environ.get("TOTEM_I2C_BUS", "1")
        self.bus_number = int(configured_bus) if bus_number is None else bus_number
        self._bus_factory = bus_factory or self._default_bus_factory
        self._bus = None
        self.initialized = False
        self._closed = False

    @staticmethod
    def _default_bus_factory(bus_number: int):
        try:
            from smbus2 import SMBus
        except ImportError:
            try:
                from smbus import SMBus
            except ImportError as exc:
                raise RuntimeError(
                    "Waveshare UPS HAT (C) requires smbus2 or the system "
                    "python3-smbus package"
                ) from exc
        return SMBus(bus_number)

    def init(self):
        if self._bus is None:
            self._bus = self._bus_factory(self.bus_number)
        try:
            self._configure_monitor()
            voltage = self._read_voltage()
            if not 2.5 <= voltage <= 5.0:
                raise RuntimeError(
                    "Waveshare UPS HAT (C) returned implausible battery "
                    "voltage {:.3f} V".format(voltage)
                )
        except Exception:
            self.close()
            raise

        self._closed = False
        self.initialized = True
        return True

    def _read_register(self, register: int) -> int:
        if self._bus is None:
            raise RuntimeError("Waveshare UPS HAT (C) driver is not initialized")
        data = self._bus.read_i2c_block_data(self.ADDRESS, register, 2)
        if len(data) != 2:
            raise RuntimeError("INA219 returned an incomplete register value")
        return (int(data[0]) << 8) | int(data[1])

    def _write_register(self, register: int, value: int) -> None:
        if self._bus is None:
            raise RuntimeError("Waveshare UPS HAT (C) driver is not initialized")
        self._bus.write_i2c_block_data(
            self.ADDRESS,
            register,
            [(value >> 8) & 0xFF, value & 0xFF],
        )

    def _configure_monitor(self) -> None:
        self._write_register(self._REG_CALIBRATION, self._CALIBRATION)
        self._write_register(self._REG_CONFIG, self._CONFIG)

    def _read_voltage(self) -> float:
        raw = self._read_register(self._REG_BUS_VOLTAGE)
        return (raw >> 3) * 0.004

    def _read_current(self) -> float:
        raw = self._read_register(self._REG_CURRENT)
        if raw & 0x8000:
            raw -= 1 << 16
        return raw * self._CURRENT_LSB_MILLIAMPS / 1000.0

    @staticmethod
    def _battery_percent(voltage: float) -> float:
        return max(0.0, min(100.0, (voltage - 3.0) / 1.2 * 100.0))

    def get_status(self) -> UPSStatus:
        if not self.initialized:
            raise RuntimeError("Waveshare UPS HAT (C) driver is not initialized")

        # INA219 current values depend on the calibration register, which may
        # reset independently of the host process.
        self._write_register(self._REG_CALIBRATION, self._CALIBRATION)
        voltage = self._read_voltage()
        current = self._read_current()
        return UPSStatus(
            model=self.MODEL,
            battery_percent=round(self._battery_percent(voltage), 1),
            voltage_volts=round(voltage, 3),
            current_amps=round(current, 3),
            power_plugged=None,
        )

    def close(self) -> None:
        if self._bus is not None:
            close = getattr(self._bus, "close", None)
            if close is not None:
                close()
        self._bus = None
        super().close()
