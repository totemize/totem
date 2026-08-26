"""Legacy NFC names translated through the canonical hardware client."""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.devices.contracts import DeviceDriver


class NFCDeviceInterface(DeviceDriver):
    """Historical NFC-driver contract retained for import compatibility."""

    @abstractmethod
    def init(self):
        """Initialize the NFC device."""
        raise NotImplementedError

    @abstractmethod
    def read(self) -> bytes:
        """Read data from the NFC device."""
        raise NotImplementedError

    @abstractmethod
    def write(self, data: bytes):
        """Write data to the NFC device."""
        raise NotImplementedError


class NFC:
    """Compatibility-only NFC facade; runtime ownership remains canonical."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name, "allow_mock": allow_mock}
        self._closed = False
        self._initialized = False

    def initialize(self):
        """Record local compatibility readiness without starting a driver."""

        self._initialized = True
        return True

    def read_data(self) -> bytes:
        return self.client.read_card()

    def write_data(self, data: bytes):
        self.client.write_card(data)

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
