"""Read-only PiSugar 2 (IP5209) battery telemetry over I2C."""

import os
from typing import Callable, Optional, Sequence, Tuple

from totem.devices.ups.ups import UPSDeviceInterface, UPSStatus


BatteryCurve = Sequence[Tuple[float, float]]


class Driver(UPSDeviceInterface):
    """PiSugar 2 driver using the IP5209 telemetry registers.

    The driver deliberately performs no register writes. Power policy remains
    under operator control; the device manager only reads battery voltage,
    current, charge estimate, and the 2-LED board's external-power signal.
    """

    ADDRESS = 0x75
    MODEL = "PiSugar 2"
    BATTERY_CURVE: BatteryCurve = (
        (4.16, 100.0),
        (4.05, 95.0),
        (4.00, 80.0),
        (3.92, 65.0),
        (3.86, 40.0),
        (3.79, 25.5),
        (3.66, 10.0),
        (3.52, 6.5),
        (3.49, 3.2),
        (3.10, 0.0),
    )

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
                    "PiSugar2 requires smbus2 or the system python3-smbus package"
                ) from exc
        return SMBus(bus_number)

    def init(self):
        if self._bus is None:
            self._bus = self._bus_factory(self.bus_number)
        try:
            voltage = self._read_voltage()
            if not 2.7 <= voltage <= 5.0:
                raise RuntimeError(
                    "PiSugar2 returned implausible battery voltage {:.3f} V".format(
                        voltage
                    )
                )
        except Exception:
            self.close()
            raise

        self._closed = False
        self.initialized = True
        return True

    def _read_register(self, register: int) -> int:
        if self._bus is None:
            raise RuntimeError("PiSugar2 driver is not initialized")
        return int(self._bus.read_byte_data(self.ADDRESS, register))

    def _read_voltage(self) -> float:
        low = self._read_register(0xA2)
        high = self._read_register(0xA3)
        if high & 0x20:
            signed = (((high & 0x3F) << 8) | low) - (1 << 14)
            millivolts = 2600.0 - signed * 0.26855
        else:
            raw = ((high & 0x1F) << 8) | low
            millivolts = 2600.0 + raw * 0.26855
        return millivolts / 1000.0

    def _read_current(self) -> float:
        low = self._read_register(0xA4)
        high = self._read_register(0xA5)
        raw = ((high & 0x3F) << 8) | low
        if high & 0x20:
            raw -= 1 << 14
        return raw * 0.745985 / 1000.0

    @classmethod
    def _battery_percent(cls, voltage: float) -> float:
        if voltage >= cls.BATTERY_CURVE[0][0]:
            return 100.0
        if voltage <= cls.BATTERY_CURVE[-1][0]:
            return 0.0

        for upper, lower in zip(cls.BATTERY_CURVE, cls.BATTERY_CURVE[1:]):
            upper_voltage, upper_percent = upper
            lower_voltage, lower_percent = lower
            if lower_voltage <= voltage <= upper_voltage:
                fraction = (voltage - lower_voltage) / (upper_voltage - lower_voltage)
                return lower_percent + fraction * (upper_percent - lower_percent)
        raise AssertionError("battery curve does not cover voltage")

    def get_status(self) -> UPSStatus:
        if not self.initialized:
            raise RuntimeError("PiSugar2 driver is not initialized")
        voltage = self._read_voltage()
        current = self._read_current()
        gpio = self._read_register(0x55)
        return UPSStatus(
            model=self.MODEL,
            battery_percent=round(self._battery_percent(voltage), 1),
            voltage_volts=round(voltage, 3),
            current_amps=round(current, 3),
            power_plugged=bool(gpio & 0x10),
        )

    def close(self) -> None:
        if self._bus is not None:
            close = getattr(self._bus, "close", None)
            if close is not None:
                close()
        self._bus = None
        super().close()
