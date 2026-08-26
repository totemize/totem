"""Legacy manager names are pure delegates over the canonical client."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, Callable

import pytest

from totem.managers.display_manager import DisplayManager
from totem.managers.network_manager import NetworkManager
from totem.managers.nfc_manager import NFCManager
from totem.managers.storage_manager import StorageManager
from totem.managers.ups_manager import UPSManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class FakeClient:
    """Local recording seam; it never owns or opens a hardware runtime."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        def invoke(*args: object, **kwargs: object) -> object:
            self.calls.append((operation, args, kwargs))
            return {
                "display_dimensions": {"width": 250, "height": 122},
                "get_capabilities": {"wifi": {"supported": True}, "bluetooth": {"supported": True}},
                "get_status": {"wifi_radio": "enabled", "bluetooth_radio": "enabled"},
                "scan_wifi_networks": [{"ssid": "Totem", "signal_percent": 80}],
            }.get(operation, operation)

        return invoke


@pytest.mark.parametrize(
    ("manager_type", "args", "kwargs", "expected"),
    [
        (DisplayManager, (), {"driver_name": "mock_eink", "allow_mock": True}, {"driver_name": "mock_eink", "allow_mock": True}),
        (UPSManager, (), {"driver_name": "pisugar2"}, {"driver_name": "pisugar2"}),
        (NFCManager, (), {"driver_name": "mock_nfc", "allow_mock": True}, {"driver_name": "mock_nfc", "allow_mock": True}),
        (StorageManager, (), {"driver_name": "filesystem", "storage_root": "/tmp/totem"}, {"driver_name": "filesystem", "storage_root": "/tmp/totem"}),
        (NetworkManager, (), {"driver_name": "mock_wifi", "bluetooth_driver_name": "mock_bluetooth", "allow_mock": True}, {"driver_name": "mock_wifi", "bluetooth_driver_name": "mock_bluetooth", "allow_mock": True}),
    ],
)
def test_manager_constructors_keep_legacy_inputs_without_initializing_hardware(
    manager_type, args, kwargs, expected
) -> None:
    client = FakeClient()
    manager = manager_type(*args, client=client, **kwargs)

    assert manager.client is client
    assert manager.legacy_config == expected
    assert client.calls == []


@pytest.mark.parametrize(
    ("manager", "operation", "args", "kwargs", "expected"),
    [
        (DisplayManager(client=FakeClient()), "clear_screen", (), {}, "clear_screen"),
        (DisplayManager(client=FakeClient()), "display_text", ("hello",), {}, "display_text"),
        (DisplayManager(client=FakeClient()), "display_image", (b"frame",), {}, "display_image"),
        (DisplayManager(client=FakeClient()), "display_bytes", (b"frame",), {}, "display_bytes"),
        (DisplayManager(client=FakeClient()), "display_encoded_image", (b"frame",), {}, "display_encoded_image"),
        (DisplayManager(client=FakeClient()), "sleep", (), {}, "sleep"),
        (DisplayManager(client=FakeClient()), "wake", (), {}, "wake"),
        (UPSManager(client=FakeClient()), "get_status", (), {}, "get_ups_status"),
        (NFCManager(client=FakeClient()), "read_card", (), {}, "read_card"),
        (NFCManager(client=FakeClient()), "write_card", ("note",), {}, "write_card"),
        (StorageManager(client=FakeClient()), "write_data", ("note.txt", b"note"), {}, "write_data"),
        (StorageManager(client=FakeClient()), "read_data", ("note.txt",), {}, "read_data"),
        (NetworkManager(client=FakeClient()), "scan_networks", (), {}, [{"SSID": "Totem", "Signal": "80"}]),
        (NetworkManager(client=FakeClient()), "scan_wifi_networks", (), {}, "scan_wifi_networks"),
        (NetworkManager(client=FakeClient()), "connect_to_network", ("Totem", "secret"), {}, "connect_to_network"),
        (NetworkManager(client=FakeClient()), "disconnect_from_network", (), {}, "disconnect_from_network"),
        (NetworkManager(client=FakeClient()), "create_hotspot", ("Totem", "secret"), {}, "create_hotspot"),
        (NetworkManager(client=FakeClient()), "stop_hotspot", (), {}, "stop_hotspot"),
        (NetworkManager(client=FakeClient()), "get_wifi_status", (), {}, "get_wifi_status"),
        (NetworkManager(client=FakeClient()), "get_capabilities", (), {}, {"wifi": {"supported": True}, "bluetooth": {"supported": True}}),
        (NetworkManager(client=FakeClient()), "get_status", (), {}, {"wifi_radio": "enabled", "bluetooth_radio": "enabled"}),
        (NetworkManager(client=FakeClient()), "get_wifi_radio_state", (), {}, "get_wifi_radio_state"),
        (NetworkManager(client=FakeClient()), "set_wifi_radio_enabled", (True,), {}, "set_wifi_radio_enabled"),
        (NetworkManager(client=FakeClient()), "get_bluetooth_radio_state", (), {}, "get_bluetooth_radio_state"),
        (NetworkManager(client=FakeClient()), "set_bluetooth_radio_enabled", (True,), {}, "set_bluetooth_radio_enabled"),
        (NetworkManager(client=FakeClient()), "start_p2p_discovery", (), {}, "start_p2p_discovery"),
        (NetworkManager(client=FakeClient()), "stop_p2p_discovery", (), {}, "stop_p2p_discovery"),
        (NetworkManager(client=FakeClient()), "list_p2p_peers", (), {}, "list_p2p_peers"),
        (NetworkManager(client=FakeClient()), "create_p2p_group", ("peer-1",), {}, "create_p2p_group"),
        (NetworkManager(client=FakeClient()), "list_p2p_groups", (), {}, "list_p2p_groups"),
        (NetworkManager(client=FakeClient()), "remove_p2p_group", ("group-1",), {}, "remove_p2p_group"),
        (NetworkManager(client=FakeClient()), "start_nan_discovery", ("totem",), {}, "start_nan_discovery"),
        (NetworkManager(client=FakeClient()), "stop_nan_discovery", ("session-1",), {}, "stop_nan_discovery"),
        (NetworkManager(client=FakeClient()), "list_nan_discovery_sessions", (), {}, "list_nan_discovery_sessions"),
        (NetworkManager(client=FakeClient()), "list_nan_matches", (), {}, "list_nan_matches"),
        (NetworkManager(client=FakeClient()), "send_nan_followup", ("match-1", b"note"), {}, "send_nan_followup"),
        (NetworkManager(client=FakeClient()), "list_nan_followups", (), {}, "list_nan_followups"),
        (NetworkManager(client=FakeClient()), "create_nan_data_path", ("match-1",), {}, "create_nan_data_path"),
        (NetworkManager(client=FakeClient()), "list_nan_data_paths", (), {}, "list_nan_data_paths"),
        (NetworkManager(client=FakeClient()), "remove_nan_data_path", ("path-1",), {}, "remove_nan_data_path"),
        (NetworkManager(client=FakeClient()), "start_bluetooth_discovery", (), {}, "start_bluetooth_discovery"),
        (NetworkManager(client=FakeClient()), "stop_bluetooth_discovery", ("session-1",), {}, "stop_bluetooth_discovery"),
        (NetworkManager(client=FakeClient()), "list_bluetooth_devices", (), {}, "list_bluetooth_devices"),
        (NetworkManager(client=FakeClient()), "register_bluetooth_advertisement", ({"name": "Totem"},), {}, "register_bluetooth_advertisement"),
        (NetworkManager(client=FakeClient()), "unregister_bluetooth_advertisement", ("advert-1",), {}, "unregister_bluetooth_advertisement"),
        (NetworkManager(client=FakeClient()), "create_l2cap_listener", ("uuid",), {}, "create_l2cap_listener"),
        (NetworkManager(client=FakeClient()), "list_l2cap_listeners", (), {}, "list_l2cap_listeners"),
        (NetworkManager(client=FakeClient()), "close_l2cap_listener", ("listener-1",), {}, "close_l2cap_listener"),
        (NetworkManager(client=FakeClient()), "connect_l2cap", ("peer", 123), {}, "connect_l2cap"),
        (NetworkManager(client=FakeClient()), "list_l2cap_connections", (), {}, "list_l2cap_connections"),
        (NetworkManager(client=FakeClient()), "close_l2cap_connection", ("connection-1",), {}, "close_l2cap_connection"),
        (NetworkManager(client=FakeClient()), "handoff_l2cap_to_fips", ("connection-1",), {}, "handoff_l2cap_to_fips"),
        (NetworkManager(client=FakeClient()), "connect_bluetooth_device", ("device-1",), {}, "connect_bluetooth_device"),
        (NetworkManager(client=FakeClient()), "disconnect_bluetooth_device", ("device-1",), {}, "disconnect_bluetooth_device"),
        (NetworkManager(client=FakeClient()), "list_gatt", ("device-1",), {}, "list_gatt"),
        (NetworkManager(client=FakeClient()), "read_gatt_characteristic", ("device-1", "char-1"), {}, "read_gatt_characteristic"),
        (NetworkManager(client=FakeClient()), "write_gatt_characteristic", ("device-1", "char-1", b"value"), {}, "write_gatt_characteristic"),
        (NetworkManager(client=FakeClient()), "subscribe_gatt_characteristic", ("device-1", "char-1"), {}, "subscribe_gatt_characteristic"),
        (NetworkManager(client=FakeClient()), "unsubscribe_gatt_characteristic", ("subscription-1",), {}, "unsubscribe_gatt_characteristic"),
    ],
)
def test_every_manager_method_delegates_to_the_client(manager, operation, args, kwargs, expected) -> None:
    result = getattr(manager, operation)(*args, **kwargs)

    assert result == expected
    assert manager.client.calls[-1][0] == operation


@pytest.mark.parametrize(
    "manager",
    [DisplayManager, UPSManager, NFCManager, StorageManager, NetworkManager],
)
def test_manager_modules_import_no_hardware_owners(manager) -> None:
    source = Path(inspect.getfile(manager)).read_text(encoding="utf-8")
    imports = [
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    ]

    assert all(
        not module.startswith(("totem.devices", "totem.hardware.builtin"))
        and "DriverRegistry" not in module
        for module in imports
    )


def test_multiple_facades_share_one_client_without_closing_the_bus() -> None:
    client = FakeClient()
    display = DisplayManager(client=client)
    nfc = NFCManager(client=client)

    display.close()
    assert nfc.read_card() == "read_card"
    assert client.calls[-1][0] == "read_card"
