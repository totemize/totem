from abc import abstractmethod
import importlib
import os
from typing import Optional
from totem.logging import logger
from totem.devices.contracts import DeviceDriver

class StorageDeviceInterface(DeviceDriver):
    @abstractmethod
    def init(self):
        """Initialize the storage device."""
        pass

    @abstractmethod
    def read_file(self, file_path):
        """Read data from file."""
        pass

    @abstractmethod
    def write_file(self, file_path, data, options=None):
        """Write data to file."""
        pass


class Storage:
    def __init__(self, driver_name: Optional[str] = None, *, storage_root=None):
        self.storage_root = storage_root
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible storage hardware detected.")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting storage hardware...")
        try:
            nvme_devices = []
            # Look for nvme devices in /dev
            for file in os.listdir('/dev/'):
                if file.startswith('nvme'):
                    nvme_devices.append(file)
            logger.debug(f"NVMe devices found: {nvme_devices}")
            
            if nvme_devices:
                logger.info("Detected storage device: generic_nvme")
                return 'generic_nvme'
        except Exception as e:
            logger.error(f"Error accessing /dev/: {e}")
            
        # Default to file system driver if hardware detection fails
        logger.warning("No NVMe hardware detected, using confined filesystem storage")
        return 'filesystem'

    def _load_driver_by_name(self, driver_name: str) -> StorageDeviceInterface:
        try:
            module_path = f"totem.devices.storage.drivers.{driver_name}"
            module = importlib.import_module(module_path)
            driver_class = getattr(module, 'Driver')
            if not issubclass(driver_class, StorageDeviceInterface):
                raise TypeError(f"{driver_name} does not implement StorageDeviceInterface")
            logger.info(f"Loaded driver: {driver_name}")
            if self.storage_root is None:
                return driver_class()
            return driver_class(root=self.storage_root)
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Error loading driver '{driver_name}': {e}")
            raise

    def initialize(self):
        result = self.driver.init()
        if result is False:
            raise RuntimeError("Storage driver failed to initialize")
        return result

    def read_file(self, file_path):
        return self.driver.read_file(file_path)

    def write_file(self, file_path, data, options=None):
        return self.driver.write_file(file_path, data, options)
