"""Legacy radio family facades must delegate through canonical clients only."""

import ast
import inspect
from pathlib import Path
from typing import Any, Callable

import pytest

from totem.devices.network.bluetooth import Bluetooth, BluetoothDeviceInterface
from totem.devices.network.network import WiFi, WiFiDeviceInterface


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class RecordingClient:
    """Local fake standing in for the one canonical hardware client."""

    def __init__(self) -> None:
        self.calls = []

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        def invoke(*args: object, **kwargs: object) -> object:
            self.calls.append((operation, args, kwargs))
            return {"operation": operation}

        return invoke


def test_wifi_preserves_operations_with_an_injected_client_only():
    client = RecordingClient()
    callback = object()
    wifi = WiFi("rpi5_onboard_wifi", allow_mock=True, client=client)

    assert wifi.legacy_config == {"driver_name": "rpi5_onboard_wifi", "allow_mock": True}
    assert wifi.initialize() is True
    assert wifi.scan_networks(5.0) == {"operation": "scan_wifi_networks"}
    assert wifi.connect("mesh", "secret", 6.0) == {"operation": "connect_to_network"}
    assert wifi.create_hotspot("mesh", "secret", 7.0) == {"operation": "create_hotspot"}
    assert wifi.disconnect(8.0) == {"operation": "disconnect_from_network"}
    assert wifi.get_status() == {"operation": "get_wifi_status"}
    assert wifi.get_radio_state() == {"operation": "get_wifi_radio_state"}
    assert wifi.set_radio_enabled(False, 9.0) == {"operation": "set_wifi_radio_enabled"}
    assert wifi.get_capabilities() == {"operation": "get_wifi_capabilities"}
    assert wifi.list_interfaces() == {"operation": "list_wifi_interfaces"}
    assert wifi.start_p2p_discovery(10, 11.0) == {"operation": "start_p2p_discovery"}
    assert wifi.stop_p2p_discovery(12.0) == {"operation": "stop_p2p_discovery"}
    assert wifi.is_p2p_discovering() == {"operation": "is_p2p_discovering"}
    assert wifi.list_p2p_peers() == {"operation": "list_p2p_peers"}
    assert wifi.create_p2p_group("peer", 13.0) == {"operation": "create_p2p_group"}
    assert wifi.list_p2p_groups() == {"operation": "list_p2p_groups"}
    assert wifi.remove_p2p_group("group", 14.0) == {"operation": "remove_p2p_group"}
    assert wifi.start_nan_discovery("totem", b"data", 15, 16.0) == {"operation": "start_nan_discovery"}
    assert wifi.stop_nan_discovery("session", 17.0) == {"operation": "stop_nan_discovery"}
    assert wifi.list_nan_discovery_sessions() == {"operation": "list_nan_discovery_sessions"}
    assert wifi.list_nan_matches("session") == {"operation": "list_nan_matches"}
    assert wifi.send_nan_followup("match", b"data", 18.0) == {"operation": "send_nan_followup"}
    assert wifi.list_nan_followups("session") == {"operation": "list_nan_followups"}
    assert wifi.create_nan_data_path("match", 4874, 19.0) == {"operation": "create_nan_data_path"}
    assert wifi.list_nan_data_paths() == {"operation": "list_nan_data_paths"}
    assert wifi.remove_nan_data_path("path", 20.0) == {"operation": "remove_nan_data_path"}
    assert wifi.set_event_callback(callback) == {"operation": "set_event_callback"}

    assert client.calls == [
        ("scan_wifi_networks", (5.0,), {}),
        ("connect_to_network", ("mesh", "secret", 6.0), {}),
        ("create_hotspot", ("mesh", "secret", 7.0), {}),
        ("disconnect_from_network", (8.0,), {}),
        ("get_wifi_status", (), {}),
        ("get_wifi_radio_state", (), {}),
        ("set_wifi_radio_enabled", (False, 9.0), {}),
        ("get_wifi_capabilities", (), {}),
        ("list_wifi_interfaces", (), {}),
        ("start_p2p_discovery", (10, 11.0), {}),
        ("stop_p2p_discovery", (12.0,), {}),
        ("is_p2p_discovering", (), {}),
        ("list_p2p_peers", (), {}),
        ("create_p2p_group", ("peer", 13.0), {}),
        ("list_p2p_groups", (), {}),
        ("remove_p2p_group", ("group", 14.0), {}),
        ("start_nan_discovery", ("totem", b"data", 15, 16.0), {}),
        ("stop_nan_discovery", ("session", 17.0), {}),
        ("list_nan_discovery_sessions", (), {}),
        ("list_nan_matches", ("session",), {}),
        ("send_nan_followup", ("match", b"data", 18.0), {}),
        ("list_nan_followups", ("session",), {}),
        ("create_nan_data_path", ("match", 4874, 19.0), {}),
        ("list_nan_data_paths", (), {}),
        ("remove_nan_data_path", ("path", 20.0), {}),
        ("set_event_callback", (callback,), {}),
    ]


def test_bluetooth_preserves_operations_with_an_injected_client_only():
    client = RecordingClient()
    callback = object()
    bluetooth = Bluetooth("bluez", allow_mock=True, client=client)

    assert bluetooth.legacy_config == {"driver_name": "bluez", "allow_mock": True}
    assert bluetooth.initialize() is True
    assert bluetooth.get_radio_state() == {"operation": "get_bluetooth_radio_state"}
    assert bluetooth.set_radio_enabled(False, 5.0) == {"operation": "set_bluetooth_radio_enabled"}
    assert bluetooth.get_capabilities() == {"operation": "get_bluetooth_capabilities"}
    assert bluetooth.start_discovery(duration_seconds=6) == {"operation": "start_bluetooth_discovery"}
    assert bluetooth.stop_discovery("discovery", 7.0) == {"operation": "stop_bluetooth_discovery"}
    assert bluetooth.discovery_session_count() == {"operation": "bluetooth_discovery_session_count"}
    assert bluetooth.list_devices() == {"operation": "list_bluetooth_devices"}
    assert bluetooth.register_advertisement({"name": "totem"}, 8.0) == {"operation": "register_bluetooth_advertisement"}
    assert bluetooth.unregister_advertisement("advertisement", 9.0) == {"operation": "unregister_bluetooth_advertisement"}
    assert bluetooth.list_advertisements() == {"operation": "list_bluetooth_advertisements"}
    assert bluetooth.create_l2cap_listener("service", 10, 11, "random", 12.0) == {"operation": "create_l2cap_listener"}
    assert bluetooth.list_l2cap_listeners() == {"operation": "list_l2cap_listeners"}
    assert bluetooth.close_l2cap_listener("listener", 13.0) == {"operation": "close_l2cap_listener"}
    assert bluetooth.connect_l2cap("peer", 14, 15, "random", 16.0) == {"operation": "connect_l2cap"}
    assert bluetooth.list_l2cap_connections() == {"operation": "list_l2cap_connections"}
    assert bluetooth.close_l2cap_connection("connection") == {"operation": "close_l2cap_connection"}
    assert bluetooth.handoff_l2cap_to_fips("connection", 17.0, {"kind": "fips"}) == {"operation": "handoff_l2cap_to_fips"}
    assert bluetooth.connect_device("device", 18.0) == {"operation": "connect_bluetooth_device"}
    assert bluetooth.disconnect_device("device", 19.0) == {"operation": "disconnect_bluetooth_device"}
    assert bluetooth.list_gatt("device") == {"operation": "list_gatt"}
    assert bluetooth.read_characteristic("device", "characteristic", 20.0) == {"operation": "read_gatt_characteristic"}
    assert bluetooth.write_characteristic("device", "characteristic", b"data", False, 21.0) == {"operation": "write_gatt_characteristic"}
    assert bluetooth.subscribe_characteristic("device", "characteristic", "subscription", 22.0) == {"operation": "subscribe_gatt_characteristic"}
    assert bluetooth.unsubscribe_characteristic("subscription", 23.0) == {"operation": "unsubscribe_gatt_characteristic"}
    assert bluetooth.set_event_callback(callback) == {"operation": "set_event_callback"}

    assert [operation for operation, _args, _kwargs in client.calls] == [
        "get_bluetooth_radio_state", "set_bluetooth_radio_enabled", "get_bluetooth_capabilities",
        "start_bluetooth_discovery", "stop_bluetooth_discovery", "bluetooth_discovery_session_count",
        "list_bluetooth_devices", "register_bluetooth_advertisement", "unregister_bluetooth_advertisement",
        "list_bluetooth_advertisements", "create_l2cap_listener", "list_l2cap_listeners",
        "close_l2cap_listener", "connect_l2cap", "list_l2cap_connections", "close_l2cap_connection",
        "handoff_l2cap_to_fips", "connect_bluetooth_device", "disconnect_bluetooth_device", "list_gatt",
        "read_gatt_characteristic", "write_gatt_characteristic", "subscribe_gatt_characteristic",
        "unsubscribe_gatt_characteristic", "set_event_callback",
    ]


def test_close_is_facade_local_and_preserves_shared_client_access():
    client = RecordingClient()
    wifi = WiFi(client=client)
    bluetooth = Bluetooth(client=client)

    wifi.close()
    bluetooth.close()

    assert wifi._closed is True
    assert bluetooth._closed is True
    assert wifi.get_status() == {"operation": "get_wifi_status"}
    assert bluetooth.list_devices() == {"operation": "list_bluetooth_devices"}


def test_public_radio_interfaces_remain_canonical_aliases():
    from totem.hardware.builtin.radio.network import (
        BluetoothDeviceInterface as CanonicalBluetoothDeviceInterface,
        WiFiDeviceInterface as CanonicalWiFiDeviceInterface,
    )

    assert WiFiDeviceInterface is CanonicalWiFiDeviceInterface
    assert BluetoothDeviceInterface is CanonicalBluetoothDeviceInterface


@pytest.mark.parametrize("facade", [WiFi, Bluetooth])
def test_wrapper_sources_have_no_backend_provider_registry_or_policy_ownership(facade):
    source = Path(inspect.getfile(facade)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    assert imports == ["__future__", "typing", "totem.compat.hardware_client", "totem.hardware.builtin.radio.network"]
    assert not {"_detect_hardware", "_load_driver_by_name"} & names
    for forbidden in ("DriverRegistry", "DriverSpec", "HardwareNotFoundError", "subprocess", "sys.", "Path(", "dbus", "NetworkManager", "BlueZ", "coexistence"):
        assert forbidden not in source
