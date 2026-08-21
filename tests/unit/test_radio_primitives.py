"""Unit coverage for capability parsing and policy-free radio lifecycles."""

from types import SimpleNamespace

import pytest

from totem.devices.network.capabilities import (
    modes_fit_combination,
    parse_iw_phy,
    parse_rfkill_json,
)
from totem.devices.network.errors import (
    RadioResourceNotFoundError,
    UnsupportedFeatureError,
    redact_secrets,
)
from totem.devices.network.dbus_runtime import DBusCallError
from totem.devices.network.models import (
    BluetoothRadioState,
    ConcurrentInterfaceCombination,
    InterfaceLimit,
    RadioBlockState,
)
from totem.managers.network_manager import NetworkManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


IW_PHY = """
Wiphy phy0
\tSupported interface modes:
\t\t * managed
\t\t * AP
\t\t * P2P-client
\t\t * P2P-GO
\t\t * P2P-device
\tBand 1:
\t\tFrequencies:
\t\t\t* 2412.0 MHz [1] (20.0 dBm)
\t\t\t* 2437.0 MHz [6] (20.0 dBm)
\t\t\t* 2484.0 MHz [14] (disabled)
\tvalid interface combinations:
\t\t * #{ managed } <= 2, #{ P2P-device } <= 1, #{ P2P-client, P2P-GO } <= 1,
\t\t   total <= 3, #channels <= 2
\t\t * #{ managed } <= 1, #{ AP } <= 1, #{ P2P-client } <= 1, #{ P2P-device } <= 1,
\t\t   total <= 4, #channels <= 1
"""


def test_iw_capability_parser_preserves_modes_channels_and_combinations():
    modes, bands, combinations = parse_iw_phy(IW_PHY)

    assert modes == ["managed", "AP", "P2P-client", "P2P-GO", "P2P-device"]
    assert bands == {"band1": [1, 6]}
    assert len(combinations) == 2
    assert combinations[0].maximum_interfaces == 3
    assert combinations[0].maximum_channels == 2
    assert combinations[0].limits[2].modes == ["P2P-client", "P2P-GO"]


def test_concurrent_interface_fit_accounts_for_shared_mode_limit():
    combination = ConcurrentInterfaceCombination(
        limits=[
            InterfaceLimit(["managed"], 2),
            InterfaceLimit(["P2P-client", "P2P-GO"], 1),
        ],
        maximum_interfaces=3,
        maximum_channels=2,
    )

    assert modes_fit_combination(["managed"], "P2P-client", combination)
    assert not modes_fit_combination(["managed", "P2P-client"], "P2P-GO", combination)
    assert not modes_fit_combination(["AP"], "P2P-client", combination)


def test_rfkill_parser_reports_soft_and_hard_blocks():
    state = parse_rfkill_json(
        '{"rfkilldevices":[{"type":"bluetooth","soft":"blocked","hard":"unblocked"}]}',
        "bluetooth",
    )

    assert state.soft_blocked
    assert not state.hard_blocked


def test_secret_redaction_is_recursive_and_covers_error_text():
    redacted = redact_secrets(
        {"password": "supersecret", "nested": ["psk=meshsecret", {"pin": "1234"}]}
    )

    assert redacted == {
        "password": "[REDACTED]",
        "nested": ["psk=[REDACTED]", {"pin": "[REDACTED]"}],
    }
    assert "supersecret" not in str(redacted)
    assert "meshsecret" not in str(redacted)


def test_mock_radios_report_real_shape_and_transition_idempotently():
    manager = NetworkManager("mock_wifi", allow_mock=True)
    events = []
    manager.set_event_callback(lambda event, data: events.append((event, data)))

    assert manager.get_status().wifi_radio.enabled
    manager.set_wifi_radio_enabled(False)
    manager.set_wifi_radio_enabled(False)
    assert manager.get_status().wifi_radio.block.soft_blocked
    assert [event for event, _ in events].count("wifi_radio_state_changed") == 1

    capabilities = manager.get_capabilities()
    assert capabilities.wifi.operations["p2p_group"].supported
    assert capabilities.wifi.aware.discovery.supported
    assert capabilities.wifi.aware.data_path.supported
    assert capabilities.wifi.aware.interface_mode == "NAN"
    assert capabilities.bluetooth.operations["gatt_client"].supported
    assert capabilities.bluetooth.l2cap.le_coc_listen.supported
    assert capabilities.bluetooth.l2cap.le_coc_connect.supported
    assert capabilities.bluetooth.l2cap.fd_handoff.supported
    assert capabilities.bluetooth.version == 9
    assert capabilities.bluetooth.manufacturer == 15
    manager.close()
    manager.close()


def test_network_manager_reports_nan_absence_as_typed_unsupported(monkeypatch):
    from totem.devices.network.drivers.network_manager_wifi import (
        NetworkManagerWiFiDriver,
    )

    driver = NetworkManagerWiFiDriver("wlan0", runtime=object())
    driver.initialized = True
    monkeypatch.setattr(driver, "_run", lambda command, timeout=20.0: IW_PHY)
    monkeypatch.setattr(driver, "_driver_info", lambda: {})

    capabilities = driver.get_capabilities()

    assert not capabilities.aware.discovery.supported
    assert not capabilities.aware.data_path.supported
    assert capabilities.aware.interface_mode is None
    assert capabilities.operations["nan_discovery"].reason == (
        "nl80211 NAN interface mode absent"
    )


def test_network_manager_detects_nan_interface_mode(monkeypatch):
    from totem.devices.network.drivers.network_manager_wifi import (
        NetworkManagerWiFiDriver,
    )

    driver = NetworkManagerWiFiDriver("wlan0", runtime=object())
    driver.initialized = True
    nan_phy = IW_PHY.replace("\t\t * AP\n", "\t\t * AP\n\t\t * NAN\n")
    monkeypatch.setattr(driver, "_run", lambda command, timeout=20.0: nan_phy)
    monkeypatch.setattr(driver, "_driver_info", lambda: {})

    capabilities = driver.get_capabilities()

    assert capabilities.aware.discovery.supported
    assert capabilities.aware.data_path.supported
    assert capabilities.aware.interface_mode == "NAN"


def test_p2p_discovery_group_and_teardown_lifecycle():
    manager = NetworkManager("mock_wifi", allow_mock=True)

    manager.start_p2p_discovery(10)
    peer = manager.list_p2p_peers()[0]
    group = manager.create_p2p_group(peer.id)
    assert manager.list_p2p_groups() == [group]

    manager.remove_p2p_group(group.id)
    manager.remove_p2p_group(group.id)
    manager.stop_p2p_discovery()
    manager.stop_p2p_discovery()
    assert manager.list_p2p_groups() == []
    manager.close()


def test_ble_sessions_do_not_cancel_each_other_and_cleanup_is_idempotent():
    manager = NetworkManager("mock_wifi", allow_mock=True)

    first = manager.start_bluetooth_discovery(duration_seconds=10)
    second = manager.start_bluetooth_discovery(duration_seconds=10)
    manager.stop_bluetooth_discovery(first)
    assert manager.bluetooth_device.discovery_session_count() == 1
    manager.stop_bluetooth_discovery(first)
    manager.stop_bluetooth_discovery(second)
    assert manager.bluetooth_device.discovery_session_count() == 0
    manager.close()


def test_ble_advertisement_and_gatt_primitive_lifecycle():
    manager = NetworkManager("mock_wifi", allow_mock=True)
    advertisement = manager.register_bluetooth_advertisement(
        {
            "type": "peripheral",
            "local_name": "Totem",
            "service_uuids": ["12345678-1234-5678-1234-56789abcdef0"],
        }
    )
    assert manager.get_status().bluetooth_advertisements == [advertisement]

    device = manager.list_bluetooth_devices()[0]
    manager.connect_bluetooth_device(device.id)
    characteristic = manager.list_gatt(device.id)[0].characteristics[0]
    manager.write_gatt_characteristic(device.id, characteristic.id, b"new")
    assert manager.read_gatt_characteristic(device.id, characteristic.id) == b"new"
    subscription = manager.subscribe_gatt_characteristic(device.id, characteristic.id)
    manager.unsubscribe_gatt_characteristic(subscription)
    manager.unsubscribe_gatt_characteristic(subscription)
    manager.unregister_bluetooth_advertisement(advertisement.id)
    manager.unregister_bluetooth_advertisement(advertisement.id)
    manager.close()


def test_disappearing_devices_fail_explicitly():
    manager = NetworkManager("mock_wifi", allow_mock=True)

    with pytest.raises(RadioResourceNotFoundError):
        manager.connect_bluetooth_device("missing")
    with pytest.raises(RadioResourceNotFoundError):
        manager.create_p2p_group("missing")
    manager.close()


def test_unsupported_features_have_stable_error_code():
    error = UnsupportedFeatureError("P2P is not available")

    assert error.code == "unsupported_feature"
    assert error.http_status == 501


def test_bluez_radio_enable_retries_transient_busy_after_unblock(monkeypatch):
    from totem.devices.network.drivers.bluez import Driver

    class Runtime:
        def __init__(self):
            self.calls = 0

        def set_property(self, *args):
            self.calls += 1
            if self.calls == 1:
                raise DBusCallError("org.bluez.Error.Busy", "")

    runtime = Runtime()
    driver = Driver(runtime=runtime)
    driver.initialized = True
    driver._adapter_path = "/org/bluez/hci0"
    states = iter(
        [
            BluetoothRadioState(
                False, False, False, False, RadioBlockState(True, False)
            ),
            BluetoothRadioState(
                True, False, False, True, RadioBlockState(False, False)
            ),
        ]
    )
    monkeypatch.setattr(driver, "get_radio_state", lambda: next(states))
    unblocks = []
    monkeypatch.setattr(
        driver, "_set_rfkill_blocked", lambda blocked, timeout: unblocks.append(blocked)
    )

    result = driver.set_radio_enabled(True, timeout=2)

    assert result.powered
    assert runtime.calls == 2
    assert unblocks == [False]


def test_bluez_advertisement_ids_are_safe_unique_dbus_path_segments():
    from totem.devices.network.drivers.bluez import _object_path_segment

    assert _object_path_segment("live-metot-adv").startswith("live_metot_adv_")
    assert _object_path_segment("live-metot-adv") != _object_path_segment(
        "live_metot_adv"
    )


def test_bluez_advertisement_omits_absent_optional_properties():
    from totem.devices.network.drivers.bluez import AdvertisementObject

    minimal = AdvertisementObject({"type": "peripheral"}, lambda: None)
    assert {prop.name for prop in minimal.introspect().properties} == {"Type"}

    populated = AdvertisementObject(
        {
            "type": "peripheral",
            "service_uuids": ["180d"],
            "service_data": {"180d": b"data"},
            "manufacturer_data": {15: b"maker"},
            "local_name": "Totem",
            "includes": ["tx-power"],
        },
        lambda: None,
    )
    assert {prop.name for prop in populated.introspect().properties} == {
        "Type",
        "ServiceUUIDs",
        "ServiceData",
        "ManufacturerData",
        "LocalName",
        "Includes",
    }


def test_network_manager_peer_signal_does_not_reenter_dbus_loop():
    from totem.devices.network.drivers.network_manager_wifi import (
        NM_WIFI_P2P,
        NetworkManagerWiFiDriver,
    )

    events = []
    driver = NetworkManagerWiFiDriver(
        "wlan0",
        runtime=object(),
        event_callback=lambda event, data: events.append((event, data)),
    )

    driver._on_message(
        SimpleNamespace(
            interface=NM_WIFI_P2P,
            member="PeerAdded",
            body=["/org/freedesktop/NetworkManager/WifiP2PPeer/1"],
        )
    )

    assert events == [
        (
            "wifi_p2p_peer_found",
            {"path": "/org/freedesktop/NetworkManager/WifiP2PPeer/1"},
        )
    ]
