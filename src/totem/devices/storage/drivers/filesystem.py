import os
from totem.devices.storage.device import StorageDeviceInterface
from totem.devices.storage.files import ConfinedStorage
from totem.logging import logger

class Driver(StorageDeviceInterface):
    def __init__(self, root=None):
        configured_root = root or os.environ.get(
            "TOTEM_STORAGE_ROOT", "/var/lib/totem/storage"
        )
        self.storage = ConfinedStorage(configured_root)

    def init(self):
        """Initialize the filesystem driver."""
        self.storage.initialize()
        logger.info(
            "Initialized filesystem storage at %s", self.storage.root
        )
        return True

    def read_file(self, file_path):
        """
        Read data from a file.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            bytes: The exact file contents
        """
        data = self.storage.read(file_path)
        logger.debug(f"Read {len(data)} bytes from {file_path}")
        return data

    def write_file(self, file_path, data, options=None):
        """
        Write data to a file.
        
        Args:
            file_path: Path to the file to write
            data: The data to write
            
        Returns:
            bool: True if successful
        """
        result = self.storage.write(file_path, data, options)
        logger.debug(f"Wrote {len(data)} bytes to {file_path}")
        return result
