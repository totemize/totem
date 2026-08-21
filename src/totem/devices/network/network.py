from abc import abstractmethod
import subprocess
import sys
from typing import Optional
from totem.logging import logger
from totem.devices.contracts import DeviceDriver
from totem.devices.registry import DriverRegistry, DriverSpec, HardwareNotFoundError


class WiFiDeviceInterface(DeviceDriver):
    @abstractmethod
    def init(self):
        """Initialize the Wi-Fi device."""
        pass

    @abstractmethod
    def scan_networks(self, timeout: float = 20.0) -> list:
        """Scan for available Wi-Fi networks."""
        pass

    @abstractmethod
    def connect(self, ssid: str, password: str, timeout: float = 30.0):
        """Connect to a Wi-Fi network."""
        pass

    @abstractmethod
    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        """Create a Wi-Fi hotspot."""
        pass

    @abstractmethod
    def disconnect(self, timeout: float = 15.0):
        """Disconnect from the current Wi-Fi network."""
        pass

    @abstractmethod
    def get_status(self) -> str:
        """Get the current Wi-Fi status."""
        pass

    @abstractmethod
    def get_radio_state(self):
        """Return structured Wi-Fi radio and rfkill state."""
        pass

    @abstractmethod
    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        """Explicitly enable or disable the Wi-Fi radio."""
        pass

    @abstractmethod
    def get_capabilities(self):
        """Return physical, mode and concurrency capabilities."""
        pass

    @abstractmethod
    def list_interfaces(self):
        """Return all active Wi-Fi and Wi-Fi Direct interfaces."""
        pass

    @abstractmethod
    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        pass

    @abstractmethod
    def stop_p2p_discovery(self, timeout: float = 15.0):
        pass

    @abstractmethod
    def is_p2p_discovering(self) -> bool:
        pass

    @abstractmethod
    def list_p2p_peers(self):
        pass

    @abstractmethod
    def create_p2p_group(self, peer_id: str, timeout: float = 45.0):
        pass

    @abstractmethod
    def list_p2p_groups(self):
        pass

    @abstractmethod
    def remove_p2p_group(self, group_id: str, timeout: float = 15.0):
        pass

    @abstractmethod
    def start_nan_discovery(
        self,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ):
        pass

    @abstractmethod
    def stop_nan_discovery(self, session_id: str, timeout: float = 15.0):
        pass

    @abstractmethod
    def list_nan_discovery_sessions(self):
        pass

    @abstractmethod
    def list_nan_matches(self, session_id: Optional[str] = None):
        pass

    @abstractmethod
    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        pass

    @abstractmethod
    def list_nan_data_paths(self):
        pass

    @abstractmethod
    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        pass


WIFI_DRIVERS = DriverRegistry(
    WiFiDeviceInterface,
    (
        DriverSpec(
            "rpi5_onboard_wifi", "totem.devices.network.drivers.rpi5_onboard_wifi"
        ),
        DriverSpec(
            "usb_wifi_adapter", "totem.devices.network.drivers.usb_wifi_adapter"
        ),
        DriverSpec(
            "mock_wifi", "totem.devices.network.drivers.mock_wifi", is_mock=True
        ),
    ),
)


class WiFi:
    def __init__(self, driver_name: Optional[str] = None, *, allow_mock: bool = False):
        self.allow_mock = allow_mock
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            elif allow_mock:
                logger.warning("No hardware detected; explicit mock mode is enabled.")
                self.driver = self._load_driver_by_name("mock_wifi")
            else:
                raise HardwareNotFoundError("No supported Wi-Fi hardware detected")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting Wi-Fi hardware...")

        # For non-Linux systems, don't attempt to use Linux-specific commands
        if not sys.platform.startswith("linux"):
            logger.info(f"Wi-Fi probing is unavailable on {sys.platform}")
            return None

        try:
            result = subprocess.check_output(["ls", "/sys/class/net"]).decode("utf-8")
            interfaces = result.strip().split("\n")
            logger.debug(f"Network interfaces found: {interfaces}")
        except Exception as e:
            logger.error(f"Error listing network interfaces: {e}")
            return None

        hardware_map = {
            "wlan0": "rpi5_onboard_wifi",
            "wlan1": "usb_wifi_adapter",
        }

        for interface in interfaces:
            driver_name = hardware_map.get(interface)
            if driver_name:
                logger.info(
                    f"Detected Wi-Fi device: {driver_name} (Interface: {interface})"
                )
                return driver_name

        logger.warning("No known Wi-Fi hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> WiFiDeviceInterface:
        driver = WIFI_DRIVERS.load(driver_name, allow_mock=self.allow_mock)
        logger.info(f"Loaded Wi-Fi driver: {driver_name}")
        return driver

    def initialize(self):
        self.driver.init()

    def set_event_callback(self, callback) -> None:
        setter = getattr(self.driver, "set_event_callback", None)
        if setter:
            setter(callback)

    def scan_networks(self, timeout: float = 20.0) -> list:
        return self.driver.scan_networks(timeout)

    def connect(self, ssid: str, password: str, timeout: float = 30.0):
        self.driver.connect(ssid, password, timeout)

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        self.driver.create_hotspot(ssid, password, timeout)

    def disconnect(self, timeout: float = 15.0):
        self.driver.disconnect(timeout)

    def get_status(self) -> str:
        return self.driver.get_status()

    def get_radio_state(self):
        return self.driver.get_radio_state()

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.driver.set_radio_enabled(enabled, timeout)

    def get_capabilities(self):
        return self.driver.get_capabilities()

    def list_interfaces(self):
        return self.driver.list_interfaces()

    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        return self.driver.start_p2p_discovery(duration_seconds, timeout)

    def stop_p2p_discovery(self, timeout: float = 15.0):
        return self.driver.stop_p2p_discovery(timeout)

    def is_p2p_discovering(self) -> bool:
        return self.driver.is_p2p_discovering()

    def list_p2p_peers(self):
        return self.driver.list_p2p_peers()

    def create_p2p_group(self, peer_id: str, timeout: float = 45.0):
        return self.driver.create_p2p_group(peer_id, timeout)

    def list_p2p_groups(self):
        return self.driver.list_p2p_groups()

    def remove_p2p_group(self, group_id: str, timeout: float = 15.0):
        return self.driver.remove_p2p_group(group_id, timeout)

    def start_nan_discovery(
        self,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ):
        return self.driver.start_nan_discovery(
            service_name, service_info, duration_seconds, timeout
        )

    def stop_nan_discovery(self, session_id: str, timeout: float = 15.0):
        return self.driver.stop_nan_discovery(session_id, timeout)

    def list_nan_discovery_sessions(self):
        return self.driver.list_nan_discovery_sessions()

    def list_nan_matches(self, session_id: Optional[str] = None):
        return self.driver.list_nan_matches(session_id)

    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        return self.driver.create_nan_data_path(match_id, port, timeout)

    def list_nan_data_paths(self):
        return self.driver.list_nan_data_paths()

    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        return self.driver.remove_nan_data_path(data_path_id, timeout)
