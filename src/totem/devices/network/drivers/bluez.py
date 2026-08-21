"""Generic BlueZ D-Bus Bluetooth/BLE driver."""

import base64
from datetime import datetime, timezone
import hashlib
import re
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional
import uuid

from dbus_next import Variant
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method

from totem.devices.network.bluetooth import BluetoothDeviceInterface
from totem.devices.network.capabilities import parse_rfkill_json
from totem.devices.network.dbus_runtime import (
    DBusCallError,
    SystemDBusRuntime,
    variant_value,
)
from totem.devices.network.drivers.network_manager_wifi import _tool
from totem.devices.network.errors import (
    InvalidRadioRequestError,
    RadioOperationError,
    RadioResourceNotFoundError,
    RadioTimeoutError,
    UnsupportedFeatureError,
)
from totem.devices.network.l2cap import L2CAPTransport
from totem.devices.network.models import (
    BLEAdvertisement,
    BLEDevice,
    BluetoothCapabilities,
    BluetoothRadioState,
    GATTCharacteristic,
    GATTService,
    L2CAPCapabilities,
    OperationSupport,
    RadioBlockState,
)
from totem.logging import logger


BLUEZ_SERVICE = "org.bluez"
OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
PROPERTIES = "org.freedesktop.DBus.Properties"
ADAPTER = "org.bluez.Adapter1"
DEVICE = "org.bluez.Device1"
ADVERTISING_MANAGER = "org.bluez.LEAdvertisingManager1"
ADVERTISEMENT = "org.bluez.LEAdvertisement1"
GATT_SERVICE = "org.bluez.GattService1"
GATT_CHARACTERISTIC = "org.bluez.GattCharacteristic1"
MAX_L2CAP_LISTENERS = 4
MAX_L2CAP_CONNECTIONS = 16
FIPS_SERVICE_UUID = "9c90b790-2cc5-42c0-9f87-c9cc40648f4c"
FIPS_L2CAP_HANDOFF_SOCKET = "/run/fips/l2cap-handoff.sock"


def _linux_l2cap_socket_support():
    required = ("AF_BLUETOOTH", "SOCK_SEQPACKET", "BTPROTO_L2CAP")
    missing = [name for name in required if not hasattr(socket, name)]
    if missing:
        return OperationSupport(
            False,
            "Linux LE L2CAP socket API unavailable ({})".format(", ".join(missing)),
        )
    return OperationSupport(True)


def _fd_handoff_support():
    if (
        not hasattr(socket, "SCM_RIGHTS")
        or not hasattr(socket, "AF_UNIX")
        or not hasattr(socket.socket, "sendmsg")
    ):
        return OperationSupport(False, "Unix SCM_RIGHTS descriptor passing unavailable")
    return OperationSupport(True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _object_path_segment(identifier: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", identifier)
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]
    return "{}_{}".format(sanitized, digest)


def _bytes_map(values: Dict[Any, Any]) -> Dict[str, str]:
    return {
        str(key): base64.b64encode(bytes(variant_value(value))).decode("ascii")
        for key, value in values.items()
    }


class AdvertisementObject(ServiceInterface):
    def __init__(
        self, specification: Dict[str, Any], release_callback: Callable[[], None]
    ):
        super().__init__(ADVERTISEMENT)
        self.specification = specification
        self.release_callback = release_callback
        optional_properties = {
            "ServiceUUIDs": bool(specification.get("service_uuids")),
            "ManufacturerData": bool(specification.get("manufacturer_data")),
            "ServiceData": bool(specification.get("service_data")),
            "Includes": bool(specification.get("includes")),
            "LocalName": bool(specification.get("local_name")),
        }
        # BlueZ distinguishes an absent optional property from an empty one.
        # dbus-next builds one property list per service instance, so filter
        # that list rather than mutating the shared class-level descriptors.
        properties = ServiceInterface._get_properties(self)
        setattr(
            self,
            "_ServiceInterface__properties",
            [
                prop
                for prop in properties
                if prop.name not in optional_properties
                or optional_properties[prop.name]
            ],
        )

    @method()
    def Release(self):
        self.release_callback()

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":  # noqa: F821
        return self.specification.get("type", "peripheral")

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":  # noqa: F722
        return self.specification.get("service_uuids", [])

    @dbus_property(access=PropertyAccess.READ)
    def ManufacturerData(self) -> "a{qv}":  # noqa: F722
        return {
            int(key): Variant("ay", bytes(value))
            for key, value in self.specification.get("manufacturer_data", {}).items()
        }

    @dbus_property(access=PropertyAccess.READ)
    def ServiceData(self) -> "a{sv}":  # noqa: F722
        return {
            str(key): Variant("ay", bytes(value))
            for key, value in self.specification.get("service_data", {}).items()
        }

    @dbus_property(access=PropertyAccess.READ)
    def Includes(self) -> "as":  # noqa: F722
        return self.specification.get("includes", [])

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":  # noqa: F821
        return self.specification.get("local_name", "")


class Driver(BluetoothDeviceInterface):
    def __init__(
        self,
        runtime: Optional[SystemDBusRuntime] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.initialized = False
        self._runtime = runtime
        self._owns_runtime = runtime is None
        self._event_callback = event_callback
        self._adapter_path: Optional[str] = None
        self._discovery_sessions: Dict[str, Dict[str, Any]] = {}
        self._discovery_timers: Dict[str, threading.Timer] = {}
        self._devices: Dict[str, Dict[str, str]] = {}
        self._advertisements: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, Dict[str, str]] = {}
        self._connected_by_manager = set()
        self._l2cap = L2CAPTransport(
            maximum_listeners=MAX_L2CAP_LISTENERS,
            maximum_connections=MAX_L2CAP_CONNECTIONS,
            accepted_callback=self._on_l2cap_accepted,
        )

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_callback:
            self._event_callback(event_type, data)

    def _on_l2cap_accepted(self, connection) -> None:
        self._emit(
            "ble_l2cap_connection_opened",
            {
                "connection_id": connection.id,
                "listener_id": connection.listener_id,
                "peer_address": connection.peer_address,
                "psm": connection.psm,
            },
        )

    def init(self):
        if self.initialized:
            return
        if self._runtime is None:
            self._runtime = SystemDBusRuntime()
        self._runtime.add_message_handler(self._on_message)
        self._adapter_path = self._find_adapter()
        self.initialized = True

    def _ready(self) -> None:
        if not self.initialized or self._runtime is None or self._adapter_path is None:
            raise RadioOperationError("Bluetooth driver is not initialized")

    def _objects(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        result = self._runtime.call(
            BLUEZ_SERVICE, "/", OBJECT_MANAGER, "GetManagedObjects"
        )
        return result[0] if result else {}

    def _find_adapter(self) -> str:
        for path, interfaces in self._objects().items():
            if ADAPTER in interfaces:
                return path
        raise UnsupportedFeatureError("BlueZ exposes no Bluetooth adapter")

    def get_radio_state(self):
        self._ready()
        props = self._runtime.get_all(BLUEZ_SERVICE, self._adapter_path, ADAPTER)
        block = self._rfkill_state(bool(props.get("Powered", False)))
        return BluetoothRadioState(
            powered=bool(props.get("Powered", False)),
            discovering=bool(props.get("Discovering", False)),
            discoverable=bool(props.get("Discoverable", False)),
            pairable=bool(props.get("Pairable", False)),
            block=block,
        )

    def _rfkill_state(self, powered: bool) -> RadioBlockState:
        import subprocess

        try:
            result = subprocess.run(
                [_tool("rfkill"), "--json"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return parse_rfkill_json(result.stdout, "bluetooth")
        except (OSError, subprocess.SubprocessError, ValueError):
            return RadioBlockState(soft_blocked=not powered, hard_blocked=False)

    def _set_rfkill_blocked(self, blocked: bool, timeout: float) -> None:
        import subprocess

        try:
            subprocess.run(
                [
                    _tool("rfkill"),
                    "block" if blocked else "unblock",
                    "bluetooth",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RadioTimeoutError(
                "Timed out changing Bluetooth rfkill state"
            ) from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RadioOperationError(
                "Unable to change the Bluetooth soft-block state"
            ) from exc

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        self._ready()
        before = self.get_radio_state()
        if before.powered == enabled and before.block.soft_blocked == (not enabled):
            return before
        if enabled:
            if before.block.hard_blocked:
                raise UnsupportedFeatureError(
                    "Bluetooth is hard-blocked by the hardware or firmware"
                )
            if before.block.soft_blocked:
                self._set_rfkill_blocked(False, timeout)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    self._runtime.set_property(
                        BLUEZ_SERVICE,
                        self._adapter_path,
                        ADAPTER,
                        "Powered",
                        "b",
                        True,
                        max(0.1, deadline - time.monotonic()),
                    )
                    break
                except DBusCallError as exc:
                    if not exc.error_name.endswith("Busy"):
                        raise
                    if time.monotonic() >= deadline:
                        raise RadioTimeoutError(
                            "Timed out waiting for the Bluetooth controller after rfkill"
                        ) from exc
                    time.sleep(0.2)
        else:
            if before.powered:
                self._runtime.set_property(
                    BLUEZ_SERVICE,
                    self._adapter_path,
                    ADAPTER,
                    "Powered",
                    "b",
                    False,
                    timeout,
                )
            self._set_rfkill_blocked(True, timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self.get_radio_state()
            if current.powered == enabled:
                self._emit("bluetooth_radio_state_changed", {"powered": enabled})
                return current
            time.sleep(0.1)
        raise RadioTimeoutError("Timed out waiting for Bluetooth radio state change")

    def get_capabilities(self):
        self._ready()
        adapter = self._runtime.get_all(BLUEZ_SERVICE, self._adapter_path, ADAPTER)
        advertising_manager_available = True
        try:
            advertising = self._runtime.get_all(
                BLUEZ_SERVICE, self._adapter_path, ADVERTISING_MANAGER
            )
        except DBusCallError:
            advertising_manager_available = False
            advertising = {}
        caps = advertising.get("SupportedCapabilities", {})
        roles = list(adapter.get("Roles", []))
        has_central = "central" in roles or "central-peripheral" in roles
        has_peripheral = "peripheral" in roles or "central-peripheral" in roles
        advertisement_instances = int(advertising.get("SupportedInstances", 0))
        advertising_supported = (
            has_peripheral
            and advertising_manager_available
            and advertisement_instances > 0
        )
        if not has_peripheral:
            advertising_reason = "peripheral role absent"
        elif not advertising_manager_available:
            advertising_reason = "BlueZ LE advertising manager absent"
        elif advertisement_instances <= 0:
            advertising_reason = "no advertisement instances available"
        else:
            advertising_reason = None
        socket_support = _linux_l2cap_socket_support()
        listen_supported = socket_support.supported and has_peripheral
        connect_supported = socket_support.supported and has_central
        listen_reason = socket_support.reason or (
            None if has_peripheral else "peripheral role absent"
        )
        connect_reason = socket_support.reason or (
            None if has_central else "central role absent"
        )
        handoff_support = _fd_handoff_support()
        return BluetoothCapabilities(
            adapter=self._adapter_path.rsplit("/", 1)[-1],
            address=str(adapter.get("Address", "")),
            address_type=adapter.get("AddressType"),
            name=adapter.get("Name"),
            version=(int(adapter["Version"]) if "Version" in adapter else None),
            manufacturer=(
                int(adapter["Manufacturer"]) if "Manufacturer" in adapter else None
            ),
            modalias=adapter.get("Modalias"),
            roles=roles,
            supported_advertisement_instances=advertisement_instances,
            active_advertisement_instances=int(advertising.get("ActiveInstances", 0)),
            supported_advertisement_includes=list(
                advertising.get("SupportedIncludes", [])
            ),
            maximum_advertisement_length=(
                int(caps["MaxAdvLen"]) if "MaxAdvLen" in caps else None
            ),
            maximum_scan_response_length=(
                int(caps["MaxScnRspLen"]) if "MaxScnRspLen" in caps else None
            ),
            operations={
                "radio_toggle": OperationSupport(True),
                "discovery": OperationSupport(
                    has_central, None if has_central else "central role absent"
                ),
                "advertising": OperationSupport(
                    advertising_supported,
                    advertising_reason,
                ),
                "connect": OperationSupport(
                    has_central, None if has_central else "central role absent"
                ),
                "gatt_client": OperationSupport(
                    has_central, None if has_central else "central role absent"
                ),
                "l2cap_coc_listen": OperationSupport(listen_supported, listen_reason),
                "l2cap_coc_connect": OperationSupport(
                    connect_supported, connect_reason
                ),
                "l2cap_coc_fd_handoff": handoff_support,
            },
            l2cap=L2CAPCapabilities(
                le_coc_listen=OperationSupport(listen_supported, listen_reason),
                le_coc_connect=OperationSupport(connect_supported, connect_reason),
                fd_handoff=handoff_support,
                maximum_listeners=MAX_L2CAP_LISTENERS,
                maximum_connections=MAX_L2CAP_CONNECTIONS,
            ),
        )

    def _apply_discovery_filter(self, timeout: float) -> None:
        uuids = sorted(
            {
                uuid_value
                for session in self._discovery_sessions.values()
                for uuid_value in session["service_uuids"]
            }
        )
        duplicate = any(
            session["duplicate_data"] for session in self._discovery_sessions.values()
        )
        filters = {
            "Transport": Variant("s", "le"),
            "DuplicateData": Variant("b", duplicate),
        }
        if uuids:
            filters["UUIDs"] = Variant("as", uuids)
        self._runtime.call(
            BLUEZ_SERVICE,
            self._adapter_path,
            ADAPTER,
            "SetDiscoveryFilter",
            "a{sv}",
            [filters],
            timeout,
        )

    def start_discovery(
        self,
        duration_seconds: int = 30,
        service_uuids=None,
        duplicate_data: bool = True,
        session_id=None,
        timeout: float = 15.0,
    ):
        self._ready()
        if not 1 <= duration_seconds <= 600:
            raise InvalidRadioRequestError(
                "BLE discovery duration must be between 1 and 600 seconds"
            )
        session_id = session_id or uuid.uuid4().hex
        if session_id in self._discovery_sessions:
            return session_id
        was_empty = not self._discovery_sessions
        self._discovery_sessions[session_id] = {
            "service_uuids": list(service_uuids or []),
            "duplicate_data": bool(duplicate_data),
        }
        try:
            self._apply_discovery_filter(timeout)
            if was_empty:
                self._runtime.call(
                    BLUEZ_SERVICE,
                    self._adapter_path,
                    ADAPTER,
                    "StartDiscovery",
                    timeout=timeout,
                )
        except Exception:
            self._discovery_sessions.pop(session_id, None)
            raise
        timer = threading.Timer(
            duration_seconds, self._expire_discovery, args=(session_id,)
        )
        timer.daemon = True
        timer.start()
        self._discovery_timers[session_id] = timer
        return session_id

    def _expire_discovery(self, session_id: str) -> None:
        try:
            self.stop_discovery(session_id)
        except RadioOperationError:
            logger.warning("Unable to expire BLE discovery session %s", session_id)

    def stop_discovery(self, session_id: str, timeout: float = 15.0):
        self._ready()
        if session_id not in self._discovery_sessions:
            return
        self._discovery_sessions.pop(session_id, None)
        timer = self._discovery_timers.pop(session_id, None)
        if timer:
            timer.cancel()
        if self._discovery_sessions:
            self._apply_discovery_filter(timeout)
            return
        try:
            self._runtime.call(
                BLUEZ_SERVICE,
                self._adapter_path,
                ADAPTER,
                "StopDiscovery",
                timeout=timeout,
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith(("NotReady", "Failed")):
                raise

    def discovery_session_count(self) -> int:
        return len(self._discovery_sessions)

    @staticmethod
    def _device_id(address: str) -> str:
        return address.lower().replace(":", "_")

    def _device_from_properties(self, path: str, props: Dict[str, Any]) -> BLEDevice:
        address = str(props.get("Address", ""))
        now = _utc_now()
        cached = self._devices.setdefault(
            path, {"first_seen_at": now, "last_seen_at": now}
        )
        cached["last_seen_at"] = now
        return BLEDevice(
            id=self._device_id(address),
            path=path,
            address=address,
            address_type=props.get("AddressType"),
            name=props.get("Alias") or props.get("Name"),
            service_uuids=list(props.get("UUIDs", [])),
            service_data=_bytes_map(props.get("ServiceData", {})),
            manufacturer_data=_bytes_map(props.get("ManufacturerData", {})),
            rssi=int(props["RSSI"]) if "RSSI" in props else None,
            tx_power=int(props["TxPower"]) if "TxPower" in props else None,
            first_seen_at=cached["first_seen_at"],
            last_seen_at=cached["last_seen_at"],
            connected=bool(props.get("Connected", False)),
            paired=bool(props.get("Paired", False)),
            services_resolved=bool(props.get("ServicesResolved", False)),
        )

    def list_devices(self):
        self._ready()
        devices = []
        prefix = self._adapter_path + "/dev_"
        for path, interfaces in self._objects().items():
            if path.startswith(prefix) and DEVICE in interfaces:
                devices.append(self._device_from_properties(path, interfaces[DEVICE]))
        return devices

    def _resolve_device(self, device_id: str) -> BLEDevice:
        for device in self.list_devices():
            if device.id == device_id.lower():
                return device
        raise RadioResourceNotFoundError("Bluetooth device was not found")

    def register_advertisement(self, specification, timeout: float = 15.0):
        self._ready()
        advertising = self.get_capabilities().operations["advertising"]
        if not advertising.supported:
            raise UnsupportedFeatureError(
                advertising.reason or "BLE advertising is unsupported"
            )
        advertisement_id = specification.get("id") or uuid.uuid4().hex
        if advertisement_id in self._advertisements:
            return self._advertisements[advertisement_id]["model"]
        path = "/org/totem/advertisements/{}".format(
            _object_path_segment(advertisement_id)
        )

        def released():
            self._advertisements.pop(advertisement_id, None)

        interface = AdvertisementObject(specification, released)
        self._runtime.export(path, interface, timeout)
        try:
            self._runtime.call(
                BLUEZ_SERVICE,
                self._adapter_path,
                ADVERTISING_MANAGER,
                "RegisterAdvertisement",
                "oa{sv}",
                [path, {}],
                timeout,
            )
        except Exception:
            self._runtime.unexport(path, interface)
            raise
        model = BLEAdvertisement(
            id=advertisement_id,
            path=path,
            type=specification.get("type", "peripheral"),
            service_uuids=list(specification.get("service_uuids", [])),
            local_name=specification.get("local_name"),
            includes=list(specification.get("includes", [])),
            registered_at=_utc_now(),
        )
        self._advertisements[advertisement_id] = {
            "interface": interface,
            "path": path,
            "model": model,
        }
        return model

    def unregister_advertisement(self, advertisement_id: str, timeout: float = 15.0):
        self._ready()
        entry = self._advertisements.get(advertisement_id)
        if entry is None:
            return
        try:
            self._runtime.call(
                BLUEZ_SERVICE,
                self._adapter_path,
                ADVERTISING_MANAGER,
                "UnregisterAdvertisement",
                "o",
                [entry["path"]],
                timeout,
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith("DoesNotExist"):
                raise
        finally:
            self._runtime.unexport(entry["path"], entry["interface"])
            self._advertisements.pop(advertisement_id, None)

    def list_advertisements(self):
        return [entry["model"] for entry in self._advertisements.values()]

    def create_l2cap_listener(
        self,
        service_uuid: str = FIPS_SERVICE_UUID,
        psm: int = 0,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        self._ready()
        support = self.get_capabilities().l2cap.le_coc_listen
        if not support.supported:
            raise UnsupportedFeatureError(
                support.reason or "LE L2CAP CoC listening is unsupported"
            )
        local_address = self.get_capabilities().address
        listener = self._l2cap.create_listener(
            local_address=local_address,
            service_uuid=service_uuid,
            psm=psm,
            mtu=mtu,
            address_type=address_type,
        )
        advertisement_id = "l2cap_{}".format(listener.id)
        try:
            self.register_advertisement(
                {
                    "id": advertisement_id,
                    "type": "peripheral",
                    "service_uuids": [service_uuid],
                    # Per-peer PSM discovery is a two-byte little-endian value
                    # under the FIPS UUID.  It carries no peer identity.
                    "service_data": {service_uuid: listener.psm.to_bytes(2, "little")},
                },
                timeout,
            )
        except Exception:
            # A listener that peers cannot discover is not a usable primitive.
            self._l2cap.close_listener(listener.id)
            raise
        return self._l2cap.set_listener_advertisement(listener.id, advertisement_id)

    def list_l2cap_listeners(self):
        return self._l2cap.list_listeners()

    def close_l2cap_listener(self, listener_id: str, timeout: float = 15.0):
        advertisement_id = self._l2cap.close_listener(listener_id)
        if advertisement_id:
            self.unregister_advertisement(advertisement_id, timeout)

    def connect_l2cap(
        self,
        peer_address: str,
        psm: int,
        mtu: int = 1024,
        address_type: str = "public",
        timeout: float = 15.0,
    ):
        self._ready()
        support = self.get_capabilities().l2cap.le_coc_connect
        if not support.supported:
            raise UnsupportedFeatureError(
                support.reason or "LE L2CAP CoC connections are unsupported"
            )
        connection = self._l2cap.connect(
            peer_address=peer_address,
            psm=psm,
            mtu=mtu,
            address_type=address_type,
            timeout=timeout,
        )
        self._emit(
            "ble_l2cap_connection_opened",
            {
                "connection_id": connection.id,
                "peer_address": connection.peer_address,
                "psm": connection.psm,
            },
        )
        return connection

    def list_l2cap_connections(self):
        return self._l2cap.list_connections()

    def close_l2cap_connection(self, connection_id: str):
        self._l2cap.close_connection(connection_id)
        self._emit("ble_l2cap_connection_closed", {"connection_id": connection_id})

    def handoff_l2cap_to_fips(
        self,
        connection_id: str,
        timeout: float = 15.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self._ready()
        support = self.get_capabilities().l2cap.fd_handoff
        if not support.supported:
            raise UnsupportedFeatureError(
                support.reason or "LE L2CAP descriptor handoff is unsupported"
            )
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            receiver.settimeout(timeout)
            receiver.connect(FIPS_L2CAP_HANDOFF_SOCKET)
            self._l2cap.handoff(connection_id, receiver, metadata)
        except (TimeoutError, socket.timeout) as exc:
            raise RadioTimeoutError("FIPS LE L2CAP handoff timed out") from exc
        except OSError as exc:
            raise RadioOperationError(
                "Could not connect to the FIPS LE L2CAP handoff socket: {}".format(exc)
            )
        finally:
            receiver.close()
        self._emit(
            "ble_l2cap_connection_handed_off",
            {"connection_id": connection_id},
        )

    def connect_device(self, device_id: str, timeout: float = 30.0):
        device = self._resolve_device(device_id)
        if device.connected:
            return device
        self._runtime.call(
            BLUEZ_SERVICE, device.path, DEVICE, "Connect", timeout=timeout
        )
        self._connected_by_manager.add(device_id.lower())
        self._emit(
            "ble_connection_changed", {"device_id": device_id, "connected": True}
        )
        return self._resolve_device(device_id)

    def disconnect_device(self, device_id: str, timeout: float = 15.0):
        device = self._resolve_device(device_id)
        if not device.connected:
            self._connected_by_manager.discard(device_id.lower())
            return device
        try:
            self._runtime.call(
                BLUEZ_SERVICE, device.path, DEVICE, "Disconnect", timeout=timeout
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith("NotConnected"):
                raise
        self._connected_by_manager.discard(device_id.lower())
        self._emit(
            "ble_connection_changed", {"device_id": device_id, "connected": False}
        )
        return self._resolve_device(device_id)

    def list_gatt(self, device_id: str):
        device = self._resolve_device(device_id)
        objects = self._objects()
        services = []
        for path, interfaces in objects.items():
            props = interfaces.get(GATT_SERVICE)
            if not props or not path.startswith(device.path + "/"):
                continue
            characteristics = []
            for char_path, char_interfaces in objects.items():
                char = char_interfaces.get(GATT_CHARACTERISTIC)
                if not char or char.get("Service") != path:
                    continue
                value = char.get("Value")
                characteristics.append(
                    GATTCharacteristic(
                        id=char_path.rsplit("/", 1)[-1],
                        path=char_path,
                        uuid=str(char.get("UUID", "")),
                        service_path=path,
                        flags=list(char.get("Flags", [])),
                        notifying=bool(char.get("Notifying", False)),
                        value_base64=(
                            base64.b64encode(bytes(value)).decode("ascii")
                            if value is not None
                            else None
                        ),
                    )
                )
            services.append(
                GATTService(
                    id=path.rsplit("/", 1)[-1],
                    path=path,
                    uuid=str(props.get("UUID", "")),
                    primary=bool(props.get("Primary", False)),
                    characteristics=characteristics,
                )
            )
        return services

    def _resolve_characteristic(
        self, device_id: str, characteristic_id: str
    ) -> GATTCharacteristic:
        for service in self.list_gatt(device_id):
            for characteristic in service.characteristics:
                if characteristic.id == characteristic_id:
                    return characteristic
        raise RadioResourceNotFoundError("GATT characteristic was not found")

    def read_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        characteristic = self._resolve_characteristic(device_id, characteristic_id)
        result = self._runtime.call(
            BLUEZ_SERVICE,
            characteristic.path,
            GATT_CHARACTERISTIC,
            "ReadValue",
            "a{sv}",
            [{}],
            timeout,
        )
        return bytes(result[0])

    def write_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        value: bytes,
        with_response: bool = True,
        timeout: float = 15.0,
    ):
        characteristic = self._resolve_characteristic(device_id, characteristic_id)
        self._runtime.call(
            BLUEZ_SERVICE,
            characteristic.path,
            GATT_CHARACTERISTIC,
            "WriteValue",
            "aya{sv}",
            [
                bytes(value),
                {"type": Variant("s", "request" if with_response else "command")},
            ],
            timeout,
        )

    def subscribe_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        characteristic = self._resolve_characteristic(device_id, characteristic_id)
        subscription_id = subscription_id or uuid.uuid4().hex
        if subscription_id in self._subscriptions:
            return subscription_id
        existing = any(
            item["path"] == characteristic.path for item in self._subscriptions.values()
        )
        if not existing:
            self._runtime.call(
                BLUEZ_SERVICE,
                characteristic.path,
                GATT_CHARACTERISTIC,
                "StartNotify",
                timeout=timeout,
            )
        self._subscriptions[subscription_id] = {
            "path": characteristic.path,
            "device_id": device_id,
            "characteristic_id": characteristic_id,
        }
        return subscription_id

    def unsubscribe_characteristic(self, subscription_id: str, timeout: float = 15.0):
        entry = self._subscriptions.pop(subscription_id, None)
        if entry is None:
            return
        if any(item["path"] == entry["path"] for item in self._subscriptions.values()):
            return
        try:
            self._runtime.call(
                BLUEZ_SERVICE,
                entry["path"],
                GATT_CHARACTERISTIC,
                "StopNotify",
                timeout=timeout,
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith(("Failed", "DoesNotExist")):
                raise

    def _on_message(self, message) -> None:
        body = variant_value(message.body)
        if (
            message.interface == OBJECT_MANAGER
            and message.member == "InterfacesAdded"
            and len(body) == 2
        ):
            path, interfaces = body
            if DEVICE in interfaces:
                device = self._device_from_properties(path, interfaces[DEVICE])
                self._emit(
                    "ble_advertisement_found",
                    {"device_id": device.id, "address": device.address},
                )
        elif (
            message.interface == OBJECT_MANAGER
            and message.member == "InterfacesRemoved"
            and len(body) == 2
        ):
            path, interfaces = body
            if DEVICE in interfaces:
                cached = self._devices.pop(path, None)
                self._emit(
                    "ble_advertisement_expired",
                    {
                        "path": path,
                        "last_seen_at": cached.get("last_seen_at") if cached else None,
                    },
                )
        elif (
            message.interface == PROPERTIES
            and message.member == "PropertiesChanged"
            and len(body) >= 2
        ):
            changed_interface, changed = body[0], body[1]
            if changed_interface == DEVICE and message.path in self._devices:
                self._devices[message.path]["last_seen_at"] = _utc_now()
                self._emit("ble_advertisement_updated", {"path": message.path})
                if "Connected" in changed:
                    self._emit(
                        "ble_connection_changed",
                        {"path": message.path, "connected": bool(changed["Connected"])},
                    )
            elif changed_interface == GATT_CHARACTERISTIC and "Value" in changed:
                value = base64.b64encode(bytes(changed["Value"])).decode("ascii")
                self._emit(
                    "gatt_notification", {"path": message.path, "value_base64": value}
                )

    def close(self):
        if getattr(self, "_closed", False):
            return
        if self.initialized:
            for listener in list(self._l2cap.list_listeners()):
                try:
                    self.close_l2cap_listener(listener.id)
                except RadioOperationError:
                    pass
            self._l2cap.close()
            for session_id in list(self._discovery_sessions):
                try:
                    self.stop_discovery(session_id)
                except RadioOperationError:
                    pass
            for advertisement_id in list(self._advertisements):
                try:
                    self.unregister_advertisement(advertisement_id)
                except RadioOperationError:
                    pass
            for subscription_id in list(self._subscriptions):
                try:
                    self.unsubscribe_characteristic(subscription_id)
                except RadioOperationError:
                    pass
            for device_id in list(self._connected_by_manager):
                try:
                    self.disconnect_device(device_id)
                except RadioOperationError:
                    pass
            self._runtime.remove_message_handler(self._on_message)
            if self._owns_runtime:
                self._runtime.close()
        super().close()
