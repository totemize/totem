from abc import ABC, abstractmethod
import importlib
import os
import subprocess
from typing import Optional
from utils.logger import logger

# src/devices/eink/eink.py

class EInkDeviceInterface(ABC):
    @abstractmethod
    def init(self):
        """Initialize the e-ink device."""
        pass

    @abstractmethod
    def clear(self):
        """Clear the e-ink display."""
        pass

    @abstractmethod
    def display_image(self, image):
        """Display an image on the e-ink screen."""
        pass

    @abstractmethod
    def display_bytes(self, image_bytes):
        """Display raw byte data on the e-ink screen."""
        pass


class EInk:
    def __init__(self, driver_name: Optional[str] = None):
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible E-Ink hardware detected.")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting E-Ink hardware...")
        try:
            spi_devices = os.listdir('/dev/')
            logger.debug(f"SPI devices found: {spi_devices}")
        except Exception as e:
            logger.error(f"Error accessing /dev/: {e}")
            return None

        hardware_map = {
            'waveshare_3in7': 'waveshare_3in7',
        }


        if 'spi0.0' in spi_devices:
            logger.info("Detected E-Ink device: waveshare_3in7")
            return 'waveshare_3in7'

        logger.warning("No known E-Ink hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> EInkDeviceInterface:
        try:
            module_path = f"devices.eink.drivers.{driver_name}"
            module = importlib.import_module(module_path)
            driver_class = getattr(module, 'Driver')
            if not issubclass(driver_class, EInkDeviceInterface):
                raise TypeError(f"{driver_name} does not implement EInkDeviceInterface")
            logger.info(f"Loaded driver: {driver_name}")
            return driver_class()
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Error loading driver '{driver_name}': {e}")
            raise

    def initialize(self):
        self.driver.init()

    def clear_display(self):
        self.driver.clear()

    def display_image(self, image):
        self.driver.display_image(image)

    def display_bytes(self, image_bytes):
        self.driver.display_bytes(image_bytes)