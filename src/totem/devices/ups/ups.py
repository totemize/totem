"""UPS device contract and driver selection."""

from abc import abstractmethod
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from totem.devices.contracts import DeviceDriver
from totem.devices.registry import DriverRegistry, DriverSpec, HardwareNotFoundError
from totem.logging import logger


@dataclass(frozen=True)
class UPSStatus:
    """A read-only snapshot of battery telemetry."""

    model: str
    battery_percent: float
    voltage_volts: float
    current_amps: float
    power_plugged: Optional[bool] = None


class UPSDeviceInterface(DeviceDriver):
    """Operations every UPS driver exposes to the device manager."""

    @abstractmethod
    def init(self):
        """Initialize and validate communication with the UPS."""
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> UPSStatus:
        """Read the current battery telemetry without changing UPS state."""
        raise NotImplementedError


UPS_DRIVERS = DriverRegistry(
    UPSDeviceInterface,
    (DriverSpec("pisugar2", "totem.devices.ups.drivers.pisugar2"),),
)


class UPS:
    """Select and expose the attached UPS through a stable primitive."""

    def __init__(self, driver_name: Optional[str] = None):
        selected = driver_name or self._detect_hardware()
        if selected is None:
            raise HardwareNotFoundError("No supported UPS hardware detected")
        self.driver = UPS_DRIVERS.load(selected)
        logger.info("Loaded UPS driver: %s", selected)

    @staticmethod
    def _detect_hardware() -> Optional[str]:
        bus_number = os.environ.get("TOTEM_I2C_BUS", "1").strip() or "1"
        if Path("/dev/i2c-{}".format(bus_number)).exists():
            # PiSugar does not bind a kernel driver, so the stable deployment
            # selection is preferred. Probe the only registered I2C driver and
            # let initialization verify address 0x75 before reporting success.
            return "pisugar2"
        return None

    def initialize(self):
        return self.driver.init()

    def get_status(self) -> UPSStatus:
        return self.driver.get_status()

    def close(self) -> None:
        self.driver.close()
