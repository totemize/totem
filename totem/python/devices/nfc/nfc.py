from abc import ABC, abstractmethod
import importlib
import os
import sys
import subprocess
from typing import Type, Optional
from utils.logger import logger

class NFCDeviceInterface(ABC):
    @abstractmethod
    def init(self):
        """Initialize the NFC device."""
        pass

    @abstractmethod
    def read(self) -> bytes:
        """Read data from the NFC device."""
        pass

    @abstractmethod
    def write(self, data: bytes):
        """Write data to the NFC device."""
        pass

class NFC:
    def __init__(self, driver_name: Optional[str] = None):
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible NFC hardware detected.")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting NFC hardware...")
        try:
            output = subprocess.check_output(['lsusb']).decode('utf-8')
            logger.debug(f"lsusb output:\n{output}")
        except Exception as e:
            logger.error(f"Error executing lsusb: {e}")
            return None

        hardware_map = {
            ('04e6', '5591'): 'acs_acr122',
            ('0483', '5740'): 'pnc532',
        }

        for line in output.splitlines():
            if 'ID' in line:
                parts = line.strip().split()
                for part in parts:
                    if 'ID' in part:
                        ids = part.split('ID')[1].strip()
                        vendor_id, product_id = ids.split(':')
                        vendor_id = vendor_id.lower()
                        product_id = product_id.lower()
                        driver_name = hardware_map.get((vendor_id, product_id))
                        if driver_name:
                            logger.info(f"Detected NFC device: {driver_name}")
                            return driver_name
        logger.warning("No known NFC hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> NFCDeviceInterface:
        try:
            module_path = f"devices.nfc.drivers.{driver_name}"
            module = importlib.import_module(module_path)
            driver_class = getattr(module, 'Driver')
            if not issubclass(driver_class, NFCDeviceInterface):
                raise TypeError(f"{driver_name} does not implement NFCDeviceInterface")
            logger.info(f"Loaded driver: {driver_name}")
            return driver_class()
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Error loading driver '{driver_name}': {e}")
            raise

    def initialize(self):
        self.driver.init()

    def read_data(self) -> bytes:
        return self.driver.read()

    def write_data(self, data: bytes):
        self.driver.write(data)
