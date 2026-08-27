"""Legacy Python facade over the one canonical NIP-5D-shaped hardware bus."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from itertools import count
from typing import Any, Dict, Optional


OPERATION_ACTIONS = {
    "clear_screen": "display.frame.clear",
    "display_dimensions": "display.frame.dimensions.get",
    "display_text": "display.text.write",
    "display_image": "display.frame.write",
    "display_image_from_file": "display.frame.write",
    "display_bytes": "display.frame.write",
    "display_encoded_image": "display.frame.write",
    "display_sleep": "display.power.sleep",
    "display_wake": "display.power.wake",
    "read_card": "nfc.tag.read",
    "write_card": "nfc.tag.write",
    "read_data": "storage.files.read",
    "write_data": "storage.files.write",
    "create_hotspot": "radio.wifi.hotspot.create",
    "connect_to_network": "radio.wifi.connection.create",
    "get_wifi_capabilities": "radio.wifi.capabilities.get",
    "get_bluetooth_capabilities": "radio.bluetooth.capabilities.get",
    "get_wifi_status": "radio.wifi.status.get",
    "get_wifi_radio_state": "radio.wifi.radio.get",
    "list_wifi_interfaces": "radio.wifi.interfaces.list",
    "is_p2p_discovering": "radio.wifi.p2p.discovery.get",
    "get_bluetooth_radio_state": "radio.bluetooth.radio.get",
    "bluetooth_discovery_session_count": "radio.bluetooth.discovery.count",
    "list_bluetooth_advertisements": "radio.bluetooth.advertisements.list",
    "set_wifi_radio_enabled": "radio.wifi.radio.set",
    "set_bluetooth_radio_enabled": "radio.bluetooth.radio.set",
    "scan_wifi_networks": "radio.wifi.networks.scan",
    "disconnect_from_network": "radio.wifi.connection.delete",
    "stop_hotspot": "radio.wifi.hotspot.delete",
    "start_p2p_discovery": "radio.wifi.p2p.discovery.create",
    "stop_p2p_discovery": "radio.wifi.p2p.discovery.delete",
    "list_p2p_peers": "radio.wifi.p2p.peers.list",
    "create_p2p_group": "radio.wifi.p2p.groups.create",
    "list_p2p_groups": "radio.wifi.p2p.groups.list",
    "remove_p2p_group": "radio.wifi.p2p.groups.delete",
    "start_nan_discovery": "radio.wifi.aware.discovery.create",
    "list_nan_discovery_sessions": "radio.wifi.aware.discovery.list",
    "stop_nan_discovery": "radio.wifi.aware.discovery.delete",
    "list_nan_matches": "radio.wifi.aware.matches.list",
    "send_nan_followup": "radio.wifi.aware.followups.create",
    "list_nan_followups": "radio.wifi.aware.followups.list",
    "create_nan_data_path": "radio.wifi.aware.data-paths.create",
    "list_nan_data_paths": "radio.wifi.aware.data-paths.list",
    "remove_nan_data_path": "radio.wifi.aware.data-paths.delete",
    "start_bluetooth_discovery": "radio.bluetooth.discovery.create",
    "stop_bluetooth_discovery": "radio.bluetooth.discovery.delete",
    "list_bluetooth_devices": "radio.bluetooth.devices.list",
    "register_bluetooth_advertisement": "radio.bluetooth.advertisements.create",
    "unregister_bluetooth_advertisement": "radio.bluetooth.advertisements.delete",
    "create_l2cap_listener": "radio.bluetooth.l2cap.listeners.create",
    "list_l2cap_listeners": "radio.bluetooth.l2cap.listeners.list",
    "close_l2cap_listener": "radio.bluetooth.l2cap.listeners.delete",
    "connect_l2cap": "radio.bluetooth.l2cap.connections.create",
    "list_l2cap_connections": "radio.bluetooth.l2cap.connections.list",
    "close_l2cap_connection": "radio.bluetooth.l2cap.connections.delete",
    "handoff_l2cap_to_fips": "radio.bluetooth.l2cap.connections.handoff",
    "connect_bluetooth_device": "radio.bluetooth.devices.connect",
    "disconnect_bluetooth_device": "radio.bluetooth.devices.disconnect",
    "list_gatt": "radio.bluetooth.gatt.services.list",
    "read_gatt_characteristic": "radio.bluetooth.gatt.characteristics.read",
    "write_gatt_characteristic": "radio.bluetooth.gatt.characteristics.write",
    "subscribe_gatt_characteristic": "radio.bluetooth.gatt.subscriptions.create",
    "unsubscribe_gatt_characteristic": "radio.bluetooth.gatt.subscriptions.delete",
    "get_ups_status": "power.telemetry.read",
}


class LegacyHardwareError(RuntimeError):
    """Stable public error propagated from the canonical bus."""

    def __init__(self, code: str, message: str = "hardware operation failed") -> None:
        super().__init__(message)
        self.code = code


class LegacyHardwareClient:
    """Adapt historical manager-shaped calls into canonical bus envelopes.

    The adapter owns neither a runtime nor a provider.  ``bus`` is intentionally
    injectable for local ASGI tests and for the composed runtime application.
    """

    def __init__(self, bus: Optional[object] = None, *, binding_ids: Optional[Mapping[str, str]] = None) -> None:
        self._bus = bus
        self._binding_ids = dict(binding_ids or {})
        self._ids = count(1)

    def call(
        self,
        action: str,
        payload: Optional[Mapping[str, object]] = None,
        *,
        attachments: Optional[Mapping[str, bytes]] = None,
    ) -> Dict[str, object]:
        if self._bus is None or not hasattr(self._bus, "dispatch"):
            raise LegacyHardwareError("host_unavailable", "hardware runtime is unavailable")
        message: Dict[str, object] = {"type": action, "id": "legacy-{}".format(next(self._ids))}
        binding_id = self._binding_ids.get(action)
        if binding_id is None:
            selector = getattr(self._bus, "default_binding_id", None)
            binding_id = selector(action) if callable(selector) else None
        if isinstance(binding_id, str) and binding_id:
            message["binding_id"] = binding_id
        if payload:
            message.update(dict(payload))
        if attachments:
            message["_attachments"] = dict(attachments)
        result = self._bus.dispatch(message)
        if not isinstance(result, Mapping):
            raise LegacyHardwareError("host_unavailable", "hardware runtime is unavailable")
        response = dict(result)
        if response.get("ok") is False:
            error = response.get("error")
            code = error.get("code") if isinstance(error, Mapping) else "request_failed"
            raise LegacyHardwareError(str(code))
        return response

    def __getattr__(self, operation: str):
        action = OPERATION_ACTIONS.get(operation)
        if action is None:
            raise AttributeError(operation)

        def invoke(*args: object, **kwargs: object) -> object:
            canonical_action, payload, attachments = self._translate(operation, action, args, kwargs)
            response = self.call(canonical_action, payload, attachments=attachments or None)
            return response.get("value", response)

        return invoke

    @staticmethod
    def _translate(
        operation: str, action: str, args: tuple[object, ...], kwargs: Mapping[str, object]
    ) -> tuple[str, Dict[str, object], Dict[str, bytes]]:
        """Translate historical calls into one exact versioned SPI request.

        The compatibility edge is the only place positional legacy values,
        bytes, and historical radio spellings are accepted.  The child sees
        only public capability fields; it never receives ``args``/``kwargs``.
        """

        if operation == "read_card" and not args and not kwargs:
            return "nfc.tag.read", {}, {}
        if operation == "write_card" and len(args) == 1 and not kwargs:
            data = LegacyHardwareClient._bytes(args[0], operation)
            return "nfc.tag.write", {"data_b64": base64.b64encode(data).decode("ascii")}, {}
        if operation == "read_data" and len(args) == 1 and not kwargs:
            return "storage.files.read", {"path": LegacyHardwareClient._text(args[0], "path")}, {}
        if operation == "write_data" and len(args) in {2, 3} and not kwargs:
            data = LegacyHardwareClient._bytes(args[1], operation)
            return "storage.files.write", {
                "path": LegacyHardwareClient._text(args[0], "path"),
                "data_b64": base64.b64encode(data).decode("ascii"),
            }, {}
        if operation in {"display_image", "display_bytes", "display_encoded_image"} and len(args) == 1 and not kwargs:
            data = LegacyHardwareClient._bytes(args[0], operation)
            return "display.frame.write", {
                "frame": {"attachment_id": "frame", "width": 250, "height": 122, "pixel_format": "mono1"}
            }, {"frame": data}
        if operation == "scan_wifi_networks" and not args and not kwargs:
            return "wifi.connection.scan", {}, {}
        if operation == "connect_to_network" and len(args) >= 1 and len(args) <= 3 and not kwargs:
            payload = {"ssid": LegacyHardwareClient._text(args[0], "ssid")}
            if len(args) > 1:
                payload["password"] = LegacyHardwareClient._text(args[1], "password", allow_empty=True)
            return "wifi.connection.connect", payload, {}
        if operation == "disconnect_from_network" and not args and not kwargs:
            return "wifi.connection.disconnect", {}, {}
        if operation == "create_hotspot" and len(args) >= 1 and len(args) <= 2 and not kwargs:
            payload = {"ssid": LegacyHardwareClient._text(args[0], "ssid")}
            if len(args) == 2:
                payload["password"] = LegacyHardwareClient._text(args[1], "password", allow_empty=True)
            return "wifi.connection.hotspot", payload, {}
        if operation == "start_bluetooth_discovery" and not args and not kwargs:
            return "bluetooth.session.discover", {}, {}
        if operation == "register_bluetooth_advertisement" and len(args) == 1 and not kwargs and isinstance(args[0], Mapping):
            return "bluetooth.session.advertise", {"name": LegacyHardwareClient._text(args[0].get("name"), "name")}, {}
        if operation == "connect_bluetooth_device" and len(args) == 1 and not kwargs:
            return "bluetooth.session.connect", {"address": LegacyHardwareClient._text(args[0], "address")}, {}
        # Some historical radio extension methods have no v1 public
        # capability yet.  Preserve their route-visible operation type while
        # keeping positional compatibility data out of the process boundary;
        # providers that still advertise one opt into this namespaced payload.
        attachments: Dict[str, bytes] = {}
        values = [LegacyHardwareClient._normalize(value, attachments) for value in args]
        named = {
            str(key): LegacyHardwareClient._normalize(value, attachments)
            for key, value in kwargs.items()
        }
        return action, {"legacy_call": {"values": values, "options": named}}, attachments

    @staticmethod
    def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
        if not isinstance(value, str) or (not allow_empty and not value.strip()):
            raise LegacyHardwareError("invalid_request")
        return value

    @staticmethod
    def _bytes(value: object, operation: str) -> bytes:
        if not isinstance(value, bytes):
            raise LegacyHardwareError("invalid_request", "{} requires bytes".format(operation))
        return value

    @staticmethod
    def _normalize(value: object, attachments: Dict[str, bytes]) -> object:
        if isinstance(value, bytes):
            attachment_id = "attachment-{}".format(len(attachments) + 1)
            attachments[attachment_id] = value
            return {"attachment_id": attachment_id}
        if isinstance(value, Mapping):
            return {str(key): LegacyHardwareClient._normalize(item, attachments) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [LegacyHardwareClient._normalize(item, attachments) for item in value]
        return value
