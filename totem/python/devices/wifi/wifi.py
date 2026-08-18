from abc import abstractmethod
import subprocess
import sys
from typing import Optional
from utils.logger import logger
from devices.contracts import DeviceDriver
from devices.registry import DriverRegistry, DriverSpec, HardwareNotFoundError

class WiFiDeviceInterface(DeviceDriver):
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


WIFI_DRIVERS = DriverRegistry(
    WiFiDeviceInterface,
    (
        DriverSpec("rpi5_onboard_wifi", "devices.wifi.drivers.rpi5_onboard_wifi"),
        DriverSpec("usb_wifi_adapter", "devices.wifi.drivers.usb_wifi_adapter"),
        DriverSpec("mock_wifi", "devices.wifi.drivers.mock_wifi", is_mock=True),
    ),
)

class WiFi:
    def __init__(
        self, driver_name: Optional[str] = None, *, allow_mock: bool = False
    ):
        self.allow_mock = allow_mock
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            elif allow_mock:
                logger.warning("No hardware detected; explicit mock mode is enabled.")
                self.driver = self._load_driver_by_name('mock_wifi')
            else:
                raise HardwareNotFoundError("No supported Wi-Fi hardware detected")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting Wi-Fi hardware...")
        
        # For non-Linux systems, don't attempt to use Linux-specific commands
        if not sys.platform.startswith('linux'):
            logger.info(f"Wi-Fi probing is unavailable on {sys.platform}")
            return None
            
        try:
            result = subprocess.check_output(['ls', '/sys/class/net']).decode('utf-8')
            interfaces = result.strip().split('\n')
            logger.debug(f"Network interfaces found: {interfaces}")
        except Exception as e:
            logger.error(f"Error listing network interfaces: {e}")
            return None

        hardware_map = {
            'wlan0': 'rpi5_onboard_wifi',
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
        driver = WIFI_DRIVERS.load(driver_name, allow_mock=self.allow_mock)
        logger.info(f"Loaded Wi-Fi driver: {driver_name}")
        return driver

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
