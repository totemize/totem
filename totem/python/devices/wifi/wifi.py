from abc import ABC, abstractmethod
import importlib
import os
import subprocess
from typing import Optional
from utils.logger import logger

class WiFiDeviceInterface(ABC):
    @abstractmethod
    def init(self):
        """Initialize the Wi-Fi device."""
        pass

    @abstractmethod
    def scan_networks(self) -> list:
        """Scan for available Wi-Fi networks."""
        pass

    @abstractmethod
    def connect(self, ssid: str, password: str):
        """Connect to a Wi-Fi network."""
        pass

    @abstractmethod
    def create_hotspot(self, ssid: str, password: str):
        """Create a Wi-Fi hotspot."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from the current Wi-Fi network."""
        pass

    @abstractmethod
    def get_status(self) -> str:
        """Get the current Wi-Fi status."""
        pass

class WiFi:
    def __init__(self, driver_name: Optional[str] = None):
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible Wi-Fi hardware detected.")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting Wi-Fi hardware...")
        try:
            result = subprocess.check_output(['ls', '/sys/class/net']).decode('utf-8')
            interfaces = result.strip().split('\n')
            logger.debug(f"Network interfaces found: {interfaces}")
        except Exception as e:
            logger.error(f"Error listing network interfaces: {e}")
            return None

        hardware_map = {
            'wlan0': 'onboard_wifi',
            'wlan1': 'usb_wifi_adapter',
        }

        for interface in interfaces:
            driver_name = hardware_map.get(interface)
            if driver_name:
                logger.info(f"Detected Wi-Fi device: {driver_name} (Interface: {interface})")
                return driver_name

        logger.warning("No known Wi-Fi hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> WiFiDeviceInterface:
        try:
            module_path = f"devices.wifi.drivers.{driver_name}"
            module = importlib.import_module(module_path)
            driver_class = getattr(module, 'Driver')
            if not issubclass(driver_class, WiFiDeviceInterface):
                raise TypeError(f"{driver_name} does not implement WiFiDeviceInterface")
            logger.info(f"Loaded Wi-Fi driver: {driver_name}")
            return driver_class()
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Error loading Wi-Fi driver '{driver_name}': {e}")
            raise

    def initialize(self):
        self.driver.init()

    def scan_networks(self) -> list:
        return self.driver.scan_networks()

    def connect(self, ssid: str, password: str):
        self.driver.connect(ssid, password)

    def create_hotspot(self, ssid: str, password: str):
        self.driver.create_hotspot(ssid, password)

    def disconnect(self):
        self.driver.disconnect()

    def get_status(self) -> str:
        return self.driver.get_status()
