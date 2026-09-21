"""Legacy UPS name translated through the canonical hardware client."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.devices.contracts import DeviceDriver


@dataclass(frozen=True)
class UPSStatus:
    """A read-only snapshot of battery telemetry."""

    model: str
    battery_percent: float
    voltage_volts: float
    current_amps: float
    power_plugged: Optional[bool] = None


class UPSDeviceInterface(DeviceDriver):
    """Historical UPS-driver contract retained for import compatibility."""

    @abstractmethod
    def init(self):
        """Initialize and validate communication with the UPS."""
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> UPSStatus:
        """Read the current battery telemetry without changing UPS state."""
        raise NotImplementedError


class UPS:
    """Compatibility-only UPS facade; telemetry ownership stays canonical."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name}
        self._closed = False
        self._initialized = False

    def initialize(self):
        """Record local compatibility readiness without starting a driver."""

        self._initialized = True
        return True

    def get_status(self) -> UPSStatus:
        return self.client.get_ups_status()

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
