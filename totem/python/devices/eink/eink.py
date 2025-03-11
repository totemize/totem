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
        
        # First, check if we're running on a Raspberry Pi 5
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            if 'Raspberry Pi 5' in cpuinfo:
                logger.info("Detected Raspberry Pi 5, using Pi 5 specific driver")
                return 'waveshare_3in7_pi5'
        except Exception as e:
            logger.error(f"Error checking Raspberry Pi version: {e}")
        
        # Check for SPI devices
        try:
            spi_devices = os.listdir('/dev/')
            spi_devices = [dev for dev in spi_devices if dev.startswith('spidev')]
            logger.debug(f"SPI devices found: {spi_devices}")
        except Exception as e:
            logger.error(f"Error accessing /dev/: {e}")
            return None

        hardware_map = {
            'waveshare_3in7': 'waveshare_3in7',
        }

        # Check if any SPI device exists
        if spi_devices:
            logger.info("Detected SPI device, assuming waveshare_3in7")
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

    def clear(self):
        """Alias for clear_display"""
        return self.clear_display()

    def display_image(self, image):
        self.driver.display_image(image)

    def display(self, image):
        """Alias for display_image"""
        return self.display_image(image)

    def display_bytes(self, image_bytes):
        self.driver.display_bytes(image_bytes)