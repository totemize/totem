"""Deterministic mock Bluetooth/BLE and GATT transport."""

import base64
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
import uuid

from totem.devices.network.bluetooth import BluetoothDeviceInterface
from totem.devices.network.errors import RadioResourceNotFoundError
from totem.devices.network.models import (
    BLEAdvertisement,
    BLEDevice,
    BluetoothCapabilities,
    BluetoothRadioState,
    GATTCharacteristic,
    GATTService,
    L2CAPCapabilities,
    L2CAPConnection,
    L2CAPListener,
    OperationSupport,
    RadioBlockState,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


class Driver(BluetoothDeviceInterface):
    IS_MOCK = True

    def __init__(self):
        self.initialized = False
        self.powered = True
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.advertisements: Dict[str, BLEAdvertisement] = {}
        self.subscriptions: Dict[str, str] = {}
        self.value = b"mock-value"
        self.connected = False
        self.l2cap_listeners: Dict[str, L2CAPListener] = {}
        self.l2cap_connections: Dict[str, L2CAPConnection] = {}
        self._next_l2cap_psm = 0x0081
        self._event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.first_seen = _now()

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self._event_callback:
            self._event_callback(event_type, data)

    def _ready(self):
        if not self.initialized:
            raise RuntimeError("Mock Bluetooth driver is not initialized")

    def init(self):
        self.initialized = True

    def get_radio_state(self):
        self._ready()
        return BluetoothRadioState(
            powered=self.powered,
            discovering=bool(self.sessions),
            discoverable=False,
            pairable=True,
            block=RadioBlockState(not self.powered, False),
        )

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        self._ready()
        changed = self.powered != enabled
        self.powered = enabled
        if changed:
            self._emit("bluetooth_radio_state_changed", {"powered": enabled})
        return self.get_radio_state()

    def get_capabilities(self):
        self._ready()
        supported = OperationSupport(True)
        return BluetoothCapabilities(
            adapter="hci-mock",
            address="02:00:00:00:10:01",
            address_type="public",
            name="mock-controller",
            version=9,
            manufacturer=15,
            modalias="usb:v1D6Bp0246d0001",
            roles=["central", "peripheral"],
            supported_advertisement_instances=5,
            active_advertisement_instances=len(self.advertisements),
            supported_advertisement_includes=["tx-power", "appearance", "local-name"],
            maximum_advertisement_length=31,
            maximum_scan_response_length=31,
            operations={
                "radio_toggle": supported,
                "discovery": supported,
                "advertising": supported,
                "connect": supported,
                "gatt_client": supported,
                "l2cap_coc_listen": supported,
                "l2cap_coc_connect": supported,
                "l2cap_coc_fd_handoff": supported,
            },
            l2cap=L2CAPCapabilities(
                le_coc_listen=supported,
                le_coc_connect=supported,
                fd_handoff=supported,
                maximum_listeners=4,
                maximum_connections=16,
            ),
        )

    def start_discovery(
        self,
        duration_seconds=30,
        service_uuids=None,
        duplicate_data=True,
        session_id=None,
        timeout=15.0,
    ):
        self._ready()
        if not 1 <= duration_seconds <= 600:
            raise ValueError("BLE discovery duration must be between 1 and 600 seconds")
        session_id = session_id or uuid.uuid4().hex
        self.sessions.setdefault(
            session_id, {"service_uuids": list(service_uuids or [])}
        )
        self._emit("ble_advertisement_found", {"device_id": "02_00_00_00_10_02"})
        return session_id

    def stop_discovery(self, session_id: str, timeout: float = 15.0):
        self._ready()
        self.sessions.pop(session_id, None)

    def discovery_session_count(self):
        return len(self.sessions)

    def list_devices(self):
        self._ready()
        return [
            BLEDevice(
                id="02_00_00_00_10_02",
                path="/mock/bluez/dev_02_00_00_00_10_02",
                address="02:00:00:00:10:02",
                address_type="public",
                name="mock-totem",
                service_uuids=["12345678-1234-5678-1234-56789abcdef0"],
                service_data={
                    "12345678-1234-5678-1234-56789abcdef0": base64.b64encode(
                        b"totem"
                    ).decode("ascii")
                },
                manufacturer_data={"65535": base64.b64encode(b"mock").decode("ascii")},
                rssi=-42,
                tx_power=4,
                first_seen_at=self.first_seen,
                last_seen_at=_now(),
                connected=self.connected,
                paired=False,
                services_resolved=self.connected,
            )
        ]

    def _device(self, device_id):
        device = self.list_devices()[0]
        if device.id != device_id.lower():
            raise RadioResourceNotFoundError("Bluetooth device was not found")
        return device

    def register_advertisement(self, specification, timeout: float = 15.0):
        self._ready()
        advertisement_id = specification.get("id") or uuid.uuid4().hex
        if advertisement_id not in self.advertisements:
            self.advertisements[advertisement_id] = BLEAdvertisement(
                id=advertisement_id,
                path="/mock/advertisements/{}".format(advertisement_id),
                type=specification.get("type", "peripheral"),
                service_uuids=list(specification.get("service_uuids", [])),
                local_name=specification.get("local_name"),
                includes=list(specification.get("includes", [])),
                registered_at=_now(),
            )
        return self.advertisements[advertisement_id]

    def unregister_advertisement(self, advertisement_id: str, timeout: float = 15.0):
        self._ready()
        self.advertisements.pop(advertisement_id, None)

    def list_advertisements(self):
        return list(self.advertisements.values())

    def create_l2cap_listener(
        self,
        service_uuid: str,
        psm: int = 0,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        self._ready()
        listener_id = uuid.uuid4().hex
        assigned_psm = psm or self._next_l2cap_psm
        if psm == 0:
            self._next_l2cap_psm += 2
        advertisement = self.register_advertisement(
            {
                "id": "l2cap_{}".format(listener_id),
                "service_uuids": [service_uuid],
            },
            timeout,
        )
        listener = L2CAPListener(
            id=listener_id,
            local_address="02:00:00:00:10:01",
            address_type=address_type,
            psm=assigned_psm,
            mtu=mtu,
            service_uuid=service_uuid,
            advertisement_id=advertisement.id,
            listening=True,
        )
        self.l2cap_listeners[listener_id] = listener
        return listener

    def list_l2cap_listeners(self):
        return list(self.l2cap_listeners.values())

    def close_l2cap_listener(self, listener_id: str, timeout: float = 15.0):
        listener = self.l2cap_listeners.pop(listener_id, None)
        if listener and listener.advertisement_id:
            self.unregister_advertisement(listener.advertisement_id, timeout)

    def connect_l2cap(
        self,
        peer_address: str,
        psm: int,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        self._ready()
        connection_id = uuid.uuid4().hex
        connection = L2CAPConnection(
            id=connection_id,
            listener_id=None,
            peer_address=peer_address,
            address_type=address_type,
            psm=psm,
            mtu=mtu,
            connected_at=_now(),
        )
        self.l2cap_connections[connection_id] = connection
        self._emit(
            "ble_l2cap_connection_opened",
            {"connection_id": connection_id, "peer_address": peer_address, "psm": psm},
        )
        return connection

    def list_l2cap_connections(self):
        return list(self.l2cap_connections.values())

    def close_l2cap_connection(self, connection_id: str):
        self.l2cap_connections.pop(connection_id, None)

    def handoff_l2cap_to_fips(
        self, connection_id: str, timeout: float = 15.0, metadata=None
    ):
        if self.l2cap_connections.pop(connection_id, None) is None:
            raise RadioResourceNotFoundError("LE L2CAP connection was not found")
        self._emit("ble_l2cap_connection_handed_off", {"connection_id": connection_id})

    def connect_device(self, device_id: str, timeout: float = 30.0):
        self._device(device_id)
        self.connected = True
        self._emit(
            "ble_connection_changed", {"device_id": device_id, "connected": True}
        )
        return self._device(device_id)

    def disconnect_device(self, device_id: str, timeout: float = 15.0):
        self._device(device_id)
        self.connected = False
        self._emit(
            "ble_connection_changed", {"device_id": device_id, "connected": False}
        )
        return self._device(device_id)

    def list_gatt(self, device_id: str):
        self._device(device_id)
        characteristic = GATTCharacteristic(
            id="char0001",
            path="/mock/gatt/service0001/char0001",
            uuid="12345678-1234-5678-1234-56789abcdef1",
            service_path="/mock/gatt/service0001",
            flags=["read", "write", "notify"],
            notifying=bool(self.subscriptions),
            value_base64=base64.b64encode(self.value).decode("ascii"),
        )
        return [
            GATTService(
                id="service0001",
                path="/mock/gatt/service0001",
                uuid="12345678-1234-5678-1234-56789abcdef0",
                primary=True,
                characteristics=[characteristic],
            )
        ]

    def _characteristic(self, device_id, characteristic_id):
        characteristic = self.list_gatt(device_id)[0].characteristics[0]
        if characteristic.id != characteristic_id:
            raise RadioResourceNotFoundError("GATT characteristic was not found")
        return characteristic

    def read_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        self._characteristic(device_id, characteristic_id)
        return self.value

    def write_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        value: bytes,
        with_response: bool = True,
        timeout: float = 15.0,
    ):
        self._characteristic(device_id, characteristic_id)
        self.value = bytes(value)

    def subscribe_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        self._characteristic(device_id, characteristic_id)
        subscription_id = subscription_id or uuid.uuid4().hex
        self.subscriptions.setdefault(subscription_id, characteristic_id)
        return subscription_id

    def unsubscribe_characteristic(self, subscription_id: str, timeout: float = 15.0):
        self.subscriptions.pop(subscription_id, None)

    def close(self):
        if getattr(self, "_closed", False):
            return
        self.sessions.clear()
        self.advertisements.clear()
        self.subscriptions.clear()
        self.connected = False
        self.l2cap_listeners.clear()
        self.l2cap_connections.clear()
        super().close()
