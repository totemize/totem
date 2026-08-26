"""Waveshare UPS HAT (C) telemetry through its injected INA219 monitor."""

import os
from typing import Callable, Optional

from totem_driver_api.capabilities.power import PowerTelemetrySnapshot

from . import PowerDriverHealth


class Driver:
    """Read UPS HAT (C) telemetry without legacy driver inheritance or registry ownership."""

    ADDRESS, MODEL = 0x43, "Waveshare UPS HAT (C)"
    _REG_CONFIG, _REG_BUS_VOLTAGE, _REG_CURRENT, _REG_CALIBRATION = 0x00, 0x02, 0x04, 0x05
    _CALIBRATION, _CONFIG, _CURRENT_LSB_MILLIAMPS = 26868, 0x0EEF, 0.1524

    def __init__(self, bus_number: Optional[int] = None, *, bus_factory: Optional[Callable[[int], object]] = None):
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
                raise RuntimeError("Waveshare UPS HAT (C) requires smbus2 or the system python3-smbus package") from exc
        return SMBus(bus_number)

    def init(self):
        if self._bus is None:
            self._bus = self._bus_factory(self.bus_number)
        try:
            self._configure_monitor()
            voltage = self._read_voltage()
            if not 2.5 <= voltage <= 5.0:
                raise RuntimeError("Waveshare UPS HAT (C) returned implausible battery voltage {:.3f} V".format(voltage))
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
        self._bus.write_i2c_block_data(self.ADDRESS, register, [(value >> 8) & 0xFF, value & 0xFF])

    def _configure_monitor(self) -> None:
        self._write_register(self._REG_CALIBRATION, self._CALIBRATION)
        self._write_register(self._REG_CONFIG, self._CONFIG)

    def _read_voltage(self) -> float:
        return (self._read_register(self._REG_BUS_VOLTAGE) >> 3) * 0.004

    def _read_current(self) -> float:
        raw = self._read_register(self._REG_CURRENT)
        if raw & 0x8000:
            raw -= 1 << 16
        return raw * self._CURRENT_LSB_MILLIAMPS / 1000.0

    @staticmethod
    def _battery_percent(voltage: float) -> float:
        return max(0.0, min(100.0, (voltage - 3.0) / 1.2 * 100.0))

    def get_status(self) -> PowerTelemetrySnapshot:
        if not self.initialized:
            raise RuntimeError("Waveshare UPS HAT (C) driver is not initialized")
        self._write_register(self._REG_CALIBRATION, self._CALIBRATION)
        voltage, current = self._read_voltage(), self._read_current()
        return PowerTelemetrySnapshot(
            self.MODEL,
            round(self._battery_percent(voltage), 1),
            round(voltage, 3),
            round(current, 3),
            None,
        )

    def health(self) -> PowerDriverHealth:
        state = "closed" if self._closed else ("ready" if self.initialized else "new")
        return PowerDriverHealth(state=state, initialized=self.initialized)

    def close(self) -> None:
        if self._bus is not None:
            close = getattr(self._bus, "close", None)
            if close is not None:
                close()
        self._bus = None
        self.initialized = False
        self._closed = True
