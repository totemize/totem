"""Legacy Bluetooth name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.hardware.builtin.radio.network import BluetoothDeviceInterface


class Bluetooth:
    """Compatibility-only Bluetooth facade; runtime and broker stay canonical."""

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

    def get_radio_state(self):
        return self.client.get_bluetooth_radio_state()

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        return self.client.set_bluetooth_radio_enabled(enabled, timeout)

    def get_capabilities(self):
        return self.client.get_bluetooth_capabilities()

    def start_discovery(self, **kwargs):
        return self.client.start_bluetooth_discovery(**kwargs)

    def stop_discovery(self, session_id: str, timeout: float = 15.0):
        return self.client.stop_bluetooth_discovery(session_id, timeout)

    def discovery_session_count(self):
        return self.client.bluetooth_discovery_session_count()

    def list_devices(self):
        return self.client.list_bluetooth_devices()

    def register_advertisement(self, specification, timeout: float = 15.0):
        return self.client.register_bluetooth_advertisement(specification, timeout)

    def unregister_advertisement(self, advertisement_id: str, timeout: float = 15.0):
        return self.client.unregister_bluetooth_advertisement(advertisement_id, timeout)

    def list_advertisements(self):
        return self.client.list_bluetooth_advertisements()

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

    def connect_device(self, device_id: str, timeout: float = 30.0):
        return self.client.connect_bluetooth_device(device_id, timeout)

    def disconnect_device(self, device_id: str, timeout: float = 15.0):
        return self.client.disconnect_bluetooth_device(device_id, timeout)

    def list_gatt(self, device_id: str):
        return self.client.list_gatt(device_id)

    def read_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        return self.client.read_gatt_characteristic(device_id, characteristic_id, timeout)

    def write_characteristic(
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

    def subscribe_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        return self.client.subscribe_gatt_characteristic(
            device_id, characteristic_id, subscription_id, timeout
        )

    def unsubscribe_characteristic(self, subscription_id: str, timeout: float = 15.0):
        return self.client.unsubscribe_gatt_characteristic(subscription_id, timeout)

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
