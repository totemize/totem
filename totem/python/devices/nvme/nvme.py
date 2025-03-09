from abc import ABC, abstractmethod
import importlib
import os
import subprocess
from typing import Optional
from utils.logger import logger

class NVMEDeviceInterface(ABC):
    @abstractmethod
    def init(self):
        """Initialize the NVME device."""
        pass

    @abstractmethod
    def read_file(self, file_path):
        """Read data from file."""
        pass

    @abstractmethod
    def write_file(self, file_path, data):
        """Write data to file."""
        pass


class NVME:
    def __init__(self, driver_name: Optional[str] = None):
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible NVME hardware detected.")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting NVME hardware...")
        try:
            nvme_devices = []
            # Look for nvme devices in /dev
            for file in os.listdir('/dev/'):
                if file.startswith('nvme'):
                    nvme_devices.append(file)
            logger.debug(f"NVME devices found: {nvme_devices}")
            
            if nvme_devices:
                logger.info("Detected NVME device: generic_nvme")
                return 'generic_nvme'
        except Exception as e:
            logger.error(f"Error accessing /dev/: {e}")
            
        # Default to file system driver if hardware detection fails
        logger.warning("No NVME hardware detected, using filesystem driver")
        return 'filesystem'

    def _load_driver_by_name(self, driver_name: str) -> NVMEDeviceInterface:
        try:
            module_path = f"devices.nvme.drivers.{driver_name}"
            module = importlib.import_module(module_path)
            driver_class = getattr(module, 'Driver')
            if not issubclass(driver_class, NVMEDeviceInterface):
                raise TypeError(f"{driver_name} does not implement NVMEDeviceInterface")
            logger.info(f"Loaded driver: {driver_name}")
            return driver_class()
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Error loading driver '{driver_name}': {e}")
            raise

    def initialize(self):
        self.driver.init()

    def read_file(self, file_path):
        return self.driver.read_file(file_path)

    def write_file(self, file_path, data):
        return self.driver.write_file(file_path, data) 