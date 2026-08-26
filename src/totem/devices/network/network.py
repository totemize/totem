"""Legacy Wi-Fi name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.hardware.builtin.radio.network import WiFiDeviceInterface


class WiFi:
    """Compatibility-only Wi-Fi facade; runtime and broker stay canonical."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name, "allow_mock": allow_mock}
        self._closed = False
        self._initialized = False

    def initialize(self):
        """Record facade readiness without selecting or starting a backend."""

        self._initialized = True
        return True

    def set_event_callback(self, callback) -> None:
        return self.client.set_event_callback(callback)

    def scan_networks(self, timeout: float = 20.0) -> list:
        return self.client.scan_wifi_networks(timeout)

    def connect(self, ssid: str, password: str, timeout: float = 30.0):
        return self.client.connect_to_network(ssid, password, timeout)

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        return self.client.create_hotspot(ssid, password, timeout)

    def disconnect(self, timeout: float = 15.0):
        return self.client.disconnect_from_network(timeout)

    def get_status(self) -> str:
        return self.client.get_wifi_status()

    def get_radio_state(self):
        return self.client.get_wifi_radio_state()

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.client.set_wifi_radio_enabled(enabled, timeout)

    def get_capabilities(self):
        return self.client.get_wifi_capabilities()

    def list_interfaces(self):
        return self.client.list_wifi_interfaces()

    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        return self.client.start_p2p_discovery(duration_seconds, timeout)

    def stop_p2p_discovery(self, timeout: float = 15.0):
        return self.client.stop_p2p_discovery(timeout)

    def is_p2p_discovering(self) -> bool:
        return self.client.is_p2p_discovering()

    def list_p2p_peers(self):
        return self.client.list_p2p_peers()

    def create_p2p_group(self, peer_id: str, timeout: float = 45.0):
        return self.client.create_p2p_group(peer_id, timeout)

    def list_p2p_groups(self):
        return self.client.list_p2p_groups()

    def remove_p2p_group(self, group_id: str, timeout: float = 15.0):
        return self.client.remove_p2p_group(group_id, timeout)

    def start_nan_discovery(
        self,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ):
        return self.client.start_nan_discovery(
            service_name, service_info, duration_seconds, timeout
        )

    def stop_nan_discovery(self, session_id: str, timeout: float = 15.0):
        return self.client.stop_nan_discovery(session_id, timeout)

    def list_nan_discovery_sessions(self):
        return self.client.list_nan_discovery_sessions()

    def list_nan_matches(self, session_id: Optional[str] = None):
        return self.client.list_nan_matches(session_id)

    def send_nan_followup(self, match_id: str, payload: bytes, timeout: float = 15.0):
        return self.client.send_nan_followup(match_id, payload, timeout)

    def list_nan_followups(self, session_id: Optional[str] = None):
        return self.client.list_nan_followups(session_id)

    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        return self.client.create_nan_data_path(match_id, port, timeout)

    def list_nan_data_paths(self):
        return self.client.list_nan_data_paths()

    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        return self.client.remove_nan_data_path(data_path_id, timeout)

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
