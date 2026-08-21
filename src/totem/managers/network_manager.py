"""Policy-free manager for the host Wi-Fi and Bluetooth controllers."""

from typing import Callable, Dict, Optional

from totem.devices.network.bluetooth import Bluetooth
from totem.devices.network.models import NetworkCapabilities, NetworkStatus
from totem.devices.network.network import WiFi
from totem.logging import logger


class NetworkManager:
    def __init__(
        self,
        driver_name: Optional[str] = None,
        bluetooth_driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
    ):
        self.wifi_device = WiFi(driver_name, allow_mock=allow_mock)
        self.wifi_device.initialize()
        if bluetooth_driver_name is None and self.wifi_device.driver.is_mock:
            bluetooth_driver_name = "mock_bluetooth"
        self.bluetooth_device = Bluetooth(bluetooth_driver_name, allow_mock=allow_mock)
        try:
            self.bluetooth_device.initialize()
        except Exception:
            self.wifi_device.driver.close()
            raise

    def set_event_callback(self, callback: Callable[[str, Dict], None]) -> None:
        self.wifi_device.set_event_callback(callback)
        self.bluetooth_device.set_event_callback(callback)

    # Existing library contract retained for compatibility.
    def scan_networks(self) -> list:
        return [
            {"SSID": network.ssid, "Signal": str(network.signal_percent)}
            for network in self.wifi_device.scan_networks()
        ]

    def scan_wifi_networks(self, timeout: float = 20.0):
        return self.wifi_device.scan_networks(timeout)

    def connect_to_network(self, ssid: str, password: str, timeout: float = 30.0):
        logger.info("Attempting to connect to Wi-Fi network %r", ssid)
        return self.wifi_device.connect(ssid, password, timeout)

    def disconnect_from_network(self, timeout: float = 15.0):
        return self.wifi_device.disconnect(timeout)

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        logger.info("Creating Wi-Fi hotspot %r", ssid)
        return self.wifi_device.create_hotspot(ssid, password, timeout)

    def stop_hotspot(self, timeout: float = 15.0):
        return self.wifi_device.disconnect(timeout)

    def get_wifi_status(self) -> str:
        return self.wifi_device.get_status()

    def get_capabilities(self):
        return NetworkCapabilities(
            wifi=self.wifi_device.get_capabilities(),
            bluetooth=self.bluetooth_device.get_capabilities(),
        )

    def get_status(self):
        return NetworkStatus(
            wifi_radio=self.wifi_device.get_radio_state(),
            wifi_interfaces=self.wifi_device.list_interfaces(),
            p2p_discovering=self.wifi_device.is_p2p_discovering(),
            p2p_groups=self.wifi_device.list_p2p_groups(),
            bluetooth_radio=self.bluetooth_device.get_radio_state(),
            bluetooth_discovery_sessions=self.bluetooth_device.discovery_session_count(),
            bluetooth_advertisements=self.bluetooth_device.list_advertisements(),
        )

    def get_wifi_radio_state(self):
        return self.wifi_device.get_radio_state()

    def set_wifi_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.wifi_device.set_radio_enabled(enabled, timeout)

    def get_bluetooth_radio_state(self):
        return self.bluetooth_device.get_radio_state()

    def set_bluetooth_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.bluetooth_device.set_radio_enabled(enabled, timeout)

    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        return self.wifi_device.start_p2p_discovery(duration_seconds, timeout)

    def stop_p2p_discovery(self, timeout: float = 15.0):
        return self.wifi_device.stop_p2p_discovery(timeout)

    def list_p2p_peers(self):
        return self.wifi_device.list_p2p_peers()

    def create_p2p_group(self, peer_id: str, timeout: float = 45.0):
        return self.wifi_device.create_p2p_group(peer_id, timeout)

    def list_p2p_groups(self):
        return self.wifi_device.list_p2p_groups()

    def remove_p2p_group(self, group_id: str, timeout: float = 15.0):
        return self.wifi_device.remove_p2p_group(group_id, timeout)

    def start_bluetooth_discovery(self, **kwargs):
        return self.bluetooth_device.start_discovery(**kwargs)

    def stop_bluetooth_discovery(self, session_id: str, timeout: float = 15.0):
        return self.bluetooth_device.stop_discovery(session_id, timeout)

    def list_bluetooth_devices(self):
        return self.bluetooth_device.list_devices()

    def register_bluetooth_advertisement(self, specification, timeout: float = 15.0):
        return self.bluetooth_device.register_advertisement(specification, timeout)

    def unregister_bluetooth_advertisement(
        self, advertisement_id: str, timeout: float = 15.0
    ):
        return self.bluetooth_device.unregister_advertisement(advertisement_id, timeout)

    def create_l2cap_listener(
        self,
        service_uuid: str,
        psm: int = 0,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        return self.bluetooth_device.create_l2cap_listener(
            service_uuid, psm, mtu, address_type, timeout
        )

    def list_l2cap_listeners(self):
        return self.bluetooth_device.list_l2cap_listeners()

    def close_l2cap_listener(self, listener_id: str, timeout: float = 15.0):
        return self.bluetooth_device.close_l2cap_listener(listener_id, timeout)

    def connect_l2cap(
        self,
        peer_address: str,
        psm: int,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        return self.bluetooth_device.connect_l2cap(
            peer_address, psm, mtu, address_type, timeout
        )

    def list_l2cap_connections(self):
        return self.bluetooth_device.list_l2cap_connections()

    def close_l2cap_connection(self, connection_id: str):
        return self.bluetooth_device.close_l2cap_connection(connection_id)

    def handoff_l2cap_to_fips(
        self, connection_id: str, timeout: float = 15.0, metadata=None
    ):
        return self.bluetooth_device.handoff_l2cap_to_fips(
            connection_id, timeout, metadata
        )

    def connect_bluetooth_device(self, device_id: str, timeout: float = 30.0):
        return self.bluetooth_device.connect_device(device_id, timeout)

    def disconnect_bluetooth_device(self, device_id: str, timeout: float = 15.0):
        return self.bluetooth_device.disconnect_device(device_id, timeout)

    def list_gatt(self, device_id: str):
        return self.bluetooth_device.list_gatt(device_id)

    def read_gatt_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        return self.bluetooth_device.read_characteristic(
            device_id, characteristic_id, timeout
        )

    def write_gatt_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        value: bytes,
        with_response: bool = True,
        timeout: float = 15.0,
    ):
        return self.bluetooth_device.write_characteristic(
            device_id, characteristic_id, value, with_response, timeout
        )

    def subscribe_gatt_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        return self.bluetooth_device.subscribe_characteristic(
            device_id, characteristic_id, subscription_id, timeout
        )

    def unsubscribe_gatt_characteristic(
        self, subscription_id: str, timeout: float = 15.0
    ):
        return self.bluetooth_device.unsubscribe_characteristic(
            subscription_id, timeout
        )

    def close(self) -> None:
        self.bluetooth_device.driver.close()
        self.wifi_device.driver.close()
