"""Legacy storage name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient


class StorageManager:
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

    def write_data(self, file_path: str, data: bytes, options: Optional[dict] = None) -> bool:
        """
        Write data to a file at the specified path.
        
        Args:
            file_path (str): Path where to write the data.
            data (bytes): Byte array data to write.
            options (Optional[dict]): A dictionary with write options. Supported options:
                - append (bool): If True, append data to file. Defaults to False.
                - atomic (bool): If True, perform atomic write. Defaults to True.
                - sync (bool): If True, force a filesystem sync after write. Defaults to False.
                - permissions (Optional[int]): File permissions to set after writing. Defaults to None.
                
        Returns:
            bool: True if write was successful.
        """
        return self.client.write_data(file_path, data, options or {})
        
    def read_data(self, file_path: str) -> bytes:
        """
        Read data from the specified file path
        
        Args:
            file_path: Path to read from
            
        Returns:
            bytes: Data read from file
        """
        return self.client.read_data(file_path)

    def close(self) -> None:
        self._closed = True
