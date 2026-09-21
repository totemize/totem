"""Legacy radio manager translated through narrow canonical capabilities."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from totem.compat.hardware_client import LegacyHardwareClient


class NetworkManager:
    """Compatibility-only Wi-Fi/Bluetooth facade with no radio policy ownership."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        bluetooth_driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {
            "driver_name": driver_name,
            "bluetooth_driver_name": bluetooth_driver_name,
            "allow_mock": allow_mock,
        }
        self._closed = False

    def set_event_callback(self, callback: Callable[[str, Dict], None]) -> None:
        self.client.set_event_callback(callback)

    def scan_networks(self) -> list:
        return [
            {"SSID": network["ssid"], "Signal": str(network["signal_percent"])}
            if isinstance(network, dict)
            else {"SSID": network.ssid, "Signal": str(network.signal_percent)}
            for network in self.client.scan_wifi_networks()
        ]

    def scan_wifi_networks(self, timeout: float = 20.0):
        return self.client.scan_wifi_networks(timeout)

    def connect_to_network(self, ssid: str, password: str, timeout: float = 30.0):
        return self.client.connect_to_network(ssid, password, timeout)

    def disconnect_from_network(self, timeout: float = 15.0):
        return self.client.disconnect_from_network(timeout)

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        return self.client.create_hotspot(ssid, password, timeout)

    def stop_hotspot(self, timeout: float = 15.0):
        return self.client.stop_hotspot(timeout)

    def get_wifi_status(self):
        return self.client.get_wifi_status()

    def get_capabilities(self):
        return {
            "wifi": self.client.get_wifi_capabilities(),
            "bluetooth": self.client.get_bluetooth_capabilities(),
        }

    def get_status(self):
        """Aggregate independent Wi-Fi and Bluetooth snapshots without policy."""

        return {
            "wifi_radio": self.client.get_wifi_radio_state(),
            "wifi_interfaces": self.client.list_wifi_interfaces(),
            "p2p_discovering": self.client.is_p2p_discovering(),
            "p2p_groups": self.client.list_p2p_groups(),
            "nan_discovery_sessions": self.client.list_nan_discovery_sessions(),
            "nan_data_paths": self.client.list_nan_data_paths(),
            "bluetooth_radio": self.client.get_bluetooth_radio_state(),
            "bluetooth_discovery_sessions": self.client.bluetooth_discovery_session_count(),
            "bluetooth_advertisements": self.client.list_bluetooth_advertisements(),
        }

    def get_wifi_radio_state(self):
        return self.client.get_wifi_radio_state()

    def set_wifi_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.client.set_wifi_radio_enabled(enabled, timeout)

    def get_bluetooth_radio_state(self):
        return self.client.get_bluetooth_radio_state()

    def set_bluetooth_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.client.set_bluetooth_radio_enabled(enabled, timeout)

    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        return self.client.start_p2p_discovery(duration_seconds, timeout)

    def stop_p2p_discovery(self, timeout: float = 15.0):
        return self.client.stop_p2p_discovery(timeout)

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

    def list_nan_matches(self, session_id=None):
        return self.client.list_nan_matches(session_id)

    def send_nan_followup(self, match_id: str, payload: bytes, timeout: float = 15.0):
        return self.client.send_nan_followup(match_id, payload, timeout)

    def list_nan_followups(self, session_id=None):
        return self.client.list_nan_followups(session_id)

    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        return self.client.create_nan_data_path(match_id, port, timeout)

    def list_nan_data_paths(self):
        return self.client.list_nan_data_paths()

    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        return self.client.remove_nan_data_path(data_path_id, timeout)

    def start_bluetooth_discovery(self, **kwargs):
        return self.client.start_bluetooth_discovery(**kwargs)

    def stop_bluetooth_discovery(self, session_id: str, timeout: float = 15.0):
        return self.client.stop_bluetooth_discovery(session_id, timeout)

    def list_bluetooth_devices(self):
        return self.client.list_bluetooth_devices()

    def register_bluetooth_advertisement(self, specification, timeout: float = 15.0):
        return self.client.register_bluetooth_advertisement(specification, timeout)

    def unregister_bluetooth_advertisement(
        self, advertisement_id: str, timeout: float = 15.0
    ):
        return self.client.unregister_bluetooth_advertisement(advertisement_id, timeout)

    def create_l2cap_listener(
        self,
        service_uuid: str,
        psm: int = 0,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        return self.client.create_l2cap_listener(
            service_uuid, psm, mtu, address_type, timeout
        )

    def list_l2cap_listeners(self):
        return self.client.list_l2cap_listeners()

    def close_l2cap_listener(self, listener_id: str, timeout: float = 15.0):
        return self.client.close_l2cap_listener(listener_id, timeout)

    def connect_l2cap(
        self,
        peer_address: str,
        psm: int,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        return self.client.connect_l2cap(peer_address, psm, mtu, address_type, timeout)

    def list_l2cap_connections(self):
        return self.client.list_l2cap_connections()

    def close_l2cap_connection(self, connection_id: str):
        return self.client.close_l2cap_connection(connection_id)

    def handoff_l2cap_to_fips(
        self, connection_id: str, timeout: float = 15.0, metadata=None
    ):
        return self.client.handoff_l2cap_to_fips(connection_id, timeout, metadata)

    def connect_bluetooth_device(self, device_id: str, timeout: float = 30.0):
        return self.client.connect_bluetooth_device(device_id, timeout)

    def disconnect_bluetooth_device(self, device_id: str, timeout: float = 15.0):
        return self.client.disconnect_bluetooth_device(device_id, timeout)

    def list_gatt(self, device_id: str):
        return self.client.list_gatt(device_id)

    def read_gatt_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        return self.client.read_gatt_characteristic(device_id, characteristic_id, timeout)

    def write_gatt_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        value: bytes,
        with_response: bool = True,
        timeout: float = 15.0,
    ):
        return self.client.write_gatt_characteristic(
            device_id, characteristic_id, value, with_response, timeout
        )

    def subscribe_gatt_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        return self.client.subscribe_gatt_characteristic(
            device_id, characteristic_id, subscription_id, timeout
        )

    def unsubscribe_gatt_characteristic(
        self, subscription_id: str, timeout: float = 15.0
    ):
        return self.client.unsubscribe_gatt_characteristic(subscription_id, timeout)

    def close(self) -> None:
        """Close this facade only; the injected client/runtime remains shared."""

        self._closed = True
