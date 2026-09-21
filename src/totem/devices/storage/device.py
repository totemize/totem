"""Legacy storage names translated through the canonical hardware client."""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.devices.contracts import DeviceDriver


class StorageDeviceInterface(DeviceDriver):
    """Historical storage-driver contract retained for import compatibility."""

    @abstractmethod
    def init(self):
        """Initialize the storage device."""
        raise NotImplementedError

    @abstractmethod
    def read_file(self, file_path):
        """Read data from file."""
        raise NotImplementedError

    @abstractmethod
    def write_file(self, file_path, data, options=None):
        """Write data to file."""
        raise NotImplementedError


class Storage:
    """Compatibility-only storage facade; the runtime owns roots and leases."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        storage_root: Optional[object] = None,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name, "storage_root": storage_root}
        self._closed = False
        self._initialized = False

    def initialize(self):
        """Record local compatibility readiness without starting a driver."""

        self._initialized = True
        return True

    def read_file(self, file_path):
        return self.client.read_data(file_path)

    def write_file(self, file_path, data, options=None):
        return self.client.write_data(file_path, data, options or {})

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
