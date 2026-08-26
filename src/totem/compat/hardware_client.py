"""Legacy Python facade over the one canonical NIP-5D-shaped hardware bus."""

from __future__ import annotations

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
            attachments: Dict[str, bytes] = {}
            normalized_args = [self._normalize(value, attachments) for value in args]
            if operation == "display_encoded_image" and attachments:
                attachment_id, value = next(iter(attachments.items()))
                del attachments[attachment_id]
                attachments["frame"] = value
                normalized_args = [{"attachment_id": "frame"}]
            normalized_kwargs = {
                key: self._normalize(value, attachments) for key, value in kwargs.items()
            }
            response = self.call(
                action,
                {"args": normalized_args, "kwargs": normalized_kwargs},
                attachments=attachments or None,
            )
            return response.get("value", response)

        return invoke

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
