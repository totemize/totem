"""Canonical Wi-Fi session protocol with no legacy registry ownership."""

from abc import ABC, abstractmethod

from typing import Optional

class WiFiDeviceInterface(ABC):
    def close(self) -> None:
        """Release optional session state; concrete sessions may extend this hook."""
        if hasattr(self, "initialized"):
            self.initialized = False
        self._closed = True
        return None

    IS_MOCK = False

    @property
    def is_mock(self) -> bool:
        return bool(self.IS_MOCK or getattr(self, "mock_mode", False))

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
    def send_nan_followup(self, match_id: str, payload: bytes, timeout: float = 15.0):
        pass

    @abstractmethod
    def list_nan_followups(self, session_id: Optional[str] = None):
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


class BluetoothDeviceInterface(ABC):
    """Canonical Bluetooth session protocol with no legacy registry ownership."""

    def close(self) -> None:
        if hasattr(self, "initialized"):
            self.initialized = False
        self._closed = True
        return None

    IS_MOCK = False

    @property
    def is_mock(self) -> bool:
        return bool(self.IS_MOCK or getattr(self, "mock_mode", False))
