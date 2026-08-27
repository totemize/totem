"""Legacy Python facade over the one canonical NIP-5D-shaped hardware bus."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from itertools import count
from typing import Any, Dict, Optional


OPERATION_ACTIONS = {
    "display_image": "display.frame.write",
    "display_bytes": "display.frame.write",
    "display_encoded_image": "display.frame.write",
    "read_card": "nfc.tag.read",
    "write_card": "nfc.tag.write",
    "read_data": "storage.files.read",
    "write_data": "storage.files.write",
    "create_hotspot": "wifi.connection.hotspot",
    "connect_to_network": "wifi.connection.connect",
    "scan_wifi_networks": "wifi.connection.scan",
    "disconnect_from_network": "wifi.connection.disconnect",
    "start_bluetooth_discovery": "bluetooth.session.discover",
    "register_bluetooth_advertisement": "bluetooth.session.advertise",
    "connect_bluetooth_device": "bluetooth.session.connect",
    "get_ups_status": "power.telemetry.read",
}

# These historical manager methods intentionally have no NIP-5D capability
# contract.  Routes which have not yet been removed return the stable
# ``unsupported_feature`` compatibility error instead of manufacturing a
# generic message that no selected provider can consume.
DEPRECATED_OPERATIONS = frozenset(
    {
        "clear_screen", "display_dimensions", "display_text", "display_image_from_file",
        "display_sleep", "display_wake", "get_wifi_capabilities",
        "get_bluetooth_capabilities", "get_wifi_status", "get_wifi_radio_state",
        "list_wifi_interfaces", "is_p2p_discovering", "get_bluetooth_radio_state",
        "bluetooth_discovery_session_count", "list_bluetooth_advertisements",
        "set_wifi_radio_enabled", "set_bluetooth_radio_enabled", "stop_hotspot",
        "start_p2p_discovery", "stop_p2p_discovery", "list_p2p_peers",
        "create_p2p_group", "list_p2p_groups", "remove_p2p_group",
        "start_nan_discovery", "list_nan_discovery_sessions", "stop_nan_discovery",
        "list_nan_matches", "send_nan_followup", "list_nan_followups",
        "create_nan_data_path", "list_nan_data_paths", "remove_nan_data_path",
        "stop_bluetooth_discovery", "list_bluetooth_devices",
        "unregister_bluetooth_advertisement", "create_l2cap_listener",
        "list_l2cap_listeners", "close_l2cap_listener", "connect_l2cap",
        "list_l2cap_connections", "close_l2cap_connection", "handoff_l2cap_to_fips",
        "disconnect_bluetooth_device", "list_gatt", "read_gatt_characteristic",
        "write_gatt_characteristic", "subscribe_gatt_characteristic",
        "unsubscribe_gatt_characteristic",
    }
)


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
            if operation in DEPRECATED_OPERATIONS:
                def unsupported(*_args: object, **_kwargs: object) -> object:
                    raise LegacyHardwareError("unsupported_feature", "legacy operation has been removed")
                return unsupported
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
        if operation == "write_data" and len(args) == 2 and not kwargs:
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
        if operation == "connect_to_network" and 1 <= len(args) <= 2 and not kwargs:
            payload = {"ssid": LegacyHardwareClient._text(args[0], "ssid")}
            if len(args) > 1:
                payload["password"] = LegacyHardwareClient._text(args[1], "password", allow_empty=True)
            return "wifi.connection.connect", payload, {}
        if operation == "disconnect_from_network" and not args and not kwargs:
            return "wifi.connection.disconnect", {}, {}
        if operation == "create_hotspot" and 1 <= len(args) <= 2 and not kwargs:
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
        if operation == "get_ups_status" and not args and not kwargs:
            return "power.telemetry.read", {}, {}
        # Compatibility is deliberately a clean break: every public operation
        # above has one provider-owned v1 message and a complete translator.
        # Keeping a generic legacy envelope would create an unrouteable public
        # operation and let arbitrary schemas cross the process boundary.
        raise LegacyHardwareError("invalid_request", "unsupported legacy operation signature")

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
