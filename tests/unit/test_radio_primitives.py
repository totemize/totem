"""Unit coverage for capability parsing and policy-free radio lifecycles."""

from types import SimpleNamespace
from array import array
import base64
import json
import os
import socket

import pytest

from totem.devices.network.capabilities import (
    modes_fit_combination,
    parse_iw_phy,
    parse_rfkill_json,
)
from totem.devices.network.errors import (
    InvalidRadioRequestError,
    RadioConflictError,
    RadioOperationError,
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
    assert capabilities.wifi.aware.followup.supported
    assert capabilities.wifi.aware.data_path.supported
    assert capabilities.wifi.aware.interface_mode == "NAN"
    assert capabilities.wifi.aware.data_interface_mode == "NAN-data"
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
    assert not capabilities.aware.followup.supported
    assert not capabilities.aware.data_path.supported
    assert capabilities.aware.interface_mode is None
    assert capabilities.aware.data_interface_mode is None
    assert capabilities.operations["nan_discovery"].reason == (
        "nl80211 NAN interface mode absent"
    )


def test_network_manager_detects_nan_interface_mode(monkeypatch):
    from totem.devices.network.drivers import network_manager_wifi

    NetworkManagerWiFiDriver = network_manager_wifi.NetworkManagerWiFiDriver

    driver = NetworkManagerWiFiDriver("wlan0", runtime=object())
    driver.initialized = True
    nan_phy = IW_PHY.replace("\t\t * AP\n", "\t\t * AP\n\t\t * NAN\n")
    monkeypatch.setattr(driver, "_run", lambda command, timeout=20.0: nan_phy)
    monkeypatch.setattr(driver, "_driver_info", lambda: {})
    monkeypatch.setattr(network_manager_wifi, "_process_has_net_admin", lambda: True)

    capabilities = driver.get_capabilities()

    assert capabilities.aware.discovery.supported
    assert capabilities.aware.followup.supported
    assert not capabilities.aware.data_path.supported
    assert capabilities.aware.data_path.reason == (
        "nl80211 NAN data interface mode absent"
    )
    assert capabilities.aware.interface_mode == "NAN"


def test_network_manager_does_not_claim_data_path_without_negotiation_backend(
    monkeypatch,
):
    from totem.devices.network.drivers import network_manager_wifi

    NetworkManagerWiFiDriver = network_manager_wifi.NetworkManagerWiFiDriver

    driver = NetworkManagerWiFiDriver("wlan0", runtime=object())
    driver.initialized = True
    nan_phy = IW_PHY.replace("\t\t * AP\n", "\t\t * AP\n\t\t * NAN\n\t\t * NAN-data\n")
    monkeypatch.setattr(driver, "_run", lambda command, timeout=20.0: nan_phy)
    monkeypatch.setattr(driver, "_driver_info", lambda: {})
    monkeypatch.setattr(network_manager_wifi, "_process_has_net_admin", lambda: True)

    capabilities = driver.get_capabilities()

    assert capabilities.aware.discovery.supported
    assert capabilities.aware.data_interface_mode == "NAN-data"
    assert not capabilities.aware.data_path.supported
    assert capabilities.aware.data_path.reason == (
        "Linux NAN data-path negotiation backend unavailable"
    )


def test_network_manager_does_not_weaken_privileges_for_nan(monkeypatch):
    from totem.devices.network.drivers import network_manager_wifi

    driver = network_manager_wifi.NetworkManagerWiFiDriver("wlan0", runtime=object())
    driver.initialized = True
    nan_phy = IW_PHY.replace("\t\t * AP\n", "\t\t * AP\n\t\t * NAN\n")
    monkeypatch.setattr(driver, "_run", lambda command, timeout=20.0: nan_phy)
    monkeypatch.setattr(driver, "_driver_info", lambda: {})
    monkeypatch.setattr(network_manager_wifi, "_process_has_net_admin", lambda: False)

    capabilities = driver.get_capabilities()

    assert capabilities.aware.interface_mode == "NAN"
    assert not capabilities.aware.discovery.supported
    assert capabilities.aware.discovery.reason == (
        "CAP_NET_ADMIN unavailable for nl80211 NAN lifecycle"
    )


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


def test_nan_controller_publish_match_and_cleanup_lifecycle():
    from totem.devices.network.nan import NanDiscoveryController

    commands = []

    def runner(arguments, timeout):
        commands.append(arguments)
        if "add_func" in arguments and "followup" in arguments:
            return "instance_id: 3, cookie: 103\n"
        if "add_func" in arguments and "publish" in arguments:
            return "instance_id: 1, cookie: 101\n"
        if "add_func" in arguments and "subscribe" in arguments:
            return "instance_id: 2, cookie: 102\n"
        return ""

    class Monitor:
        def __init__(self):
            self.stdout = []
            self.terminated = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            return 0

        def kill(self):
            self.terminated = True

    monitor = Monitor()
    events = []
    controller = NanDiscoveryController(
        phy_name="phy9",
        interface="totemnan0",
        iw_path="/usr/bin/iw",
        runner=runner,
        popen_factory=lambda *args, **kwargs: monitor,
        event_callback=lambda event, data: events.append((event, data)),
        maximum_followups=2,
    )

    session = controller.start_session(
        service_name="myco.fips.v1",
        service_info=b'{"port":4873}',
        duration_seconds=60,
    )
    match = controller.process_event_line(
        "NAN(cookie=101): DiscoveryResult, peer_id=7, local_id=1, "
        "peer_mac=02:00:00:00:20:02, info=cGVlci1pbmZv"
    )

    assert session.publish_cookie == 101
    assert session.subscribe_cookie == 102
    assert base64.b64decode(session.service_info_base64) == b'{"port":4873}'
    assert match is not None
    assert base64.b64decode(match.service_info_base64) == b"peer-info"
    assert controller.list_matches(session.id) == [match]
    assert events[0][0] == "wifi_nan_match_found"
    publish = next(command for command in commands if "publish" in command)
    assert "eyJwb3J0Ijo0ODczfQ" in publish
    sent = controller.send_followup(match.id, b"npub1example|4873")
    received = controller.process_event_line(
        "NAN(cookie=101): FollowUpReceive, peer_id=7, local_id=1, "
        "peer_mac=02:00:00:00:20:02, info=npub1peer|4873"
    )
    assert sent.direction == "sent"
    assert base64.b64decode(sent.payload_base64) == b"npub1example|4873"
    assert received is not None
    assert received.direction == "received"
    assert base64.b64decode(received.payload_base64) == b"npub1peer|4873"
    assert controller.list_followups(session.id) == [sent, received]
    followup_command = next(command for command in commands if "followup" in command)
    assert followup_command == [
        "/usr/bin/iw",
        "dev",
        "totemnan0",
        "nan",
        "add_func",
        "type",
        "followup",
        "name",
        "myco.fips.v1",
        "info",
        "npub1example|4873",
        "flw_up_id",
        "1",
        "flw_up_req_id",
        "7",
        "flw_up_dest",
        "02:00:00:00:20:02",
    ]
    newest = controller.send_followup(match.id, b"newest")
    assert controller.list_followups(session.id) == [received, newest]
    assert [
        "/usr/bin/iw",
        "phy",
        "phy9",
        "interface",
        "add",
        "totemnan0",
        "type",
        "__nan",
    ] in commands

    controller.stop_session(session.id)
    controller.stop_session(session.id)
    assert monitor.terminated
    assert controller.list_sessions() == []
    assert controller.list_followups() == []
    assert [command[-1] for command in commands if "rm_func" in command] == [
        "101",
        "102",
    ]
    assert ["/usr/bin/iw", "dev", "totemnan0", "del"] in commands
    controller.close()


def test_nan_controller_rolls_back_cluster_when_subscription_fails():
    from totem.devices.network.nan import NanDiscoveryController

    commands = []

    def runner(arguments, timeout):
        commands.append(arguments)
        if "publish" in arguments:
            return "instance_id: 1, cookie: 101\n"
        if "subscribe" in arguments:
            raise RadioOperationError("subscribe failed")
        return ""

    class Monitor:
        stdout = []

        def terminate(self):
            pass

        def wait(self, timeout):
            return 0

        def kill(self):
            pass

    controller = NanDiscoveryController(
        phy_name="phy9",
        interface="totemnan0",
        iw_path="iw",
        runner=runner,
        popen_factory=lambda *args, **kwargs: Monitor(),
    )

    with pytest.raises(RadioOperationError, match="subscribe failed"):
        controller.start_session(service_name="myco.fips.v1")

    assert ["iw", "dev", "totemnan0", "nan", "rm_func", "cookie", "101"] in commands
    assert ["iw", "dev", "totemnan0", "nan", "stop"] in commands
    assert ["iw", "dev", "totemnan0", "del"] in commands
    assert controller.list_sessions() == []


def test_nan_followup_rejects_unrepresentable_or_oversized_payloads():
    from totem.devices.network.nan import NanDiscoveryController

    controller = NanDiscoveryController(
        phy_name="phy9",
        interface="totemnan0",
        iw_path="iw",
        runner=lambda arguments, timeout: "",
    )

    for payload in (b"\xff", b"line\nbreak", b"x" * 256):
        with pytest.raises(InvalidRadioRequestError) as exc_info:
            controller.send_followup("missing", payload)
        assert getattr(exc_info.value, "code", None) == "invalid_radio_request"


def test_l2cap_transport_assigns_psm_and_closes_listener_idempotently():
    from totem.devices.network.l2cap import L2CAPTransport

    class FakeChannel:
        def __init__(self):
            self.closed = False
            self.bound = None

        def settimeout(self, timeout):
            pass

        def setsockopt(self, level, option, value):
            pass

        def bind(self, address):
            self.bound = address

        def listen(self, backlog):
            pass

        def getsockname(self):
            return (self.bound[0], self.bound[1] or 0x0081)

        def accept(self):
            if self.closed:
                raise OSError("closed")
            raise socket.timeout()

        def close(self):
            self.closed = True

    channels = []

    def factory(*args):
        channel = FakeChannel()
        channels.append(channel)
        return channel

    transport = L2CAPTransport(socket_factory=factory, maximum_listeners=1)
    listener = transport.create_listener(
        local_address="02:00:00:00:10:01",
        service_uuid="9c90b790-2cc5-42c0-9f87-c9cc40648f4c",
    )

    assert listener.psm == 0x0081
    assert listener.mtu == 1024
    with pytest.raises(RadioConflictError) as exc_info:
        transport.create_listener(
            local_address="02:00:00:00:10:01",
            service_uuid="9c90b790-2cc5-42c0-9f87-c9cc40648f4c",
        )
    assert getattr(exc_info.value, "code", None) == "radio_concurrency_conflict"
    transport.close_listener(listener.id)
    transport.close_listener(listener.id)
    assert channels[0].closed
    transport.close()


def test_l2cap_handoff_passes_only_descriptor_and_bounded_metadata_to_fips():
    from totem.devices.network.l2cap import L2CAPTransport
    from totem.devices.network.models import L2CAPConnection

    transport = L2CAPTransport()
    channel, peer = socket.socketpair()
    receiver, fips = socket.socketpair()
    connection = L2CAPConnection(
        id="connection-1",
        listener_id=None,
        peer_address="02:00:00:00:10:02",
        address_type="public",
        psm=0x0081,
        mtu=1024,
        connected_at="2026-08-21T00:00:00+00:00",
    )
    transport._connections[connection.id] = {
        "model": connection,
        "socket": channel,
    }

    try:
        transport.handoff(connection.id, receiver, {"lane": "ble"})
        payload, ancillary, _, _ = fips.recvmsg(
            4096, socket.CMSG_SPACE(array("i").itemsize)
        )
        message = json.loads(payload)
        descriptor_data = next(
            data
            for level, kind, data in ancillary
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS
        )
        descriptors = array("i")
        descriptors.frombytes(descriptor_data[: descriptors.itemsize])
        transferred = descriptors[0]
        try:
            assert os.fstat(transferred)
        finally:
            os.close(transferred)
    finally:
        receiver.close()
        fips.close()
        peer.close()

    assert message == {
        "connection": {
            "address_type": "public",
            "id": "connection-1",
            "mtu": 1024,
            "peer_address": "02:00:00:00:10:02",
            "psm": 0x0081,
        },
        "metadata": {"lane": "ble"},
        "protocol": "fips-l2cap-v1",
    }
    assert transport.list_connections() == []


def test_l2cap_failed_mtu_setup_releases_capacity_and_socket():
    from totem.devices.network.l2cap import L2CAPTransport

    class RejectedChannel:
        def __init__(self):
            self.closed = False

        def setsockopt(self, level, option, value):
            raise OSError("MTU rejected")

        def close(self):
            self.closed = True

    channels = []

    def factory(*args):
        channel = RejectedChannel()
        channels.append(channel)
        return channel

    transport = L2CAPTransport(socket_factory=factory, maximum_listeners=1)
    for _ in range(2):
        with pytest.raises(RadioOperationError, match="receive MTU"):
            transport.create_listener(
                local_address="02:00:00:00:10:01",
                service_uuid="9c90b790-2cc5-42c0-9f87-c9cc40648f4c",
            )

    assert all(channel.closed for channel in channels)


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


def test_mock_l2cap_listener_connection_and_fips_handoff_lifecycle():
    manager = NetworkManager("mock_wifi", allow_mock=True)
    listener = manager.create_l2cap_listener("9c90b790-2cc5-42c0-9f87-c9cc40648f4c")
    connection = manager.connect_l2cap("02:00:00:00:10:02", listener.psm)

    assert manager.list_l2cap_listeners() == [listener]
    assert manager.list_l2cap_connections() == [connection]
    manager.handoff_l2cap_to_fips(connection.id)
    assert manager.list_l2cap_connections() == []
    manager.close_l2cap_listener(listener.id)
    manager.close_l2cap_listener(listener.id)
    assert manager.list_l2cap_listeners() == []
    manager.close()


def test_mock_nan_match_data_path_uses_scoped_ipv6_and_tears_down():
    manager = NetworkManager("mock_wifi", allow_mock=True)
    session = manager.start_nan_discovery(
        "myco.fips.v1", b'{"port":4873}', duration_seconds=60
    )
    match = manager.list_nan_matches(session.id)[0]
    data_path = manager.create_nan_data_path(match.id)

    assert data_path.interface == "aware_data0"
    assert data_path.local_ipv6 == "fe80::1%aware_data0"
    assert data_path.peer_ipv6 == "fe80::2%aware_data0"
    assert data_path.port == 4873
    assert manager.list_nan_data_paths() == [data_path]
    manager.remove_nan_data_path(data_path.id)
    manager.remove_nan_data_path(data_path.id)
    manager.stop_nan_discovery(session.id)
    manager.stop_nan_discovery(session.id)
    assert manager.list_nan_data_paths() == []
    assert manager.list_nan_discovery_sessions() == []
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


def test_bluez_l2cap_advertises_assigned_psm_as_fips_service_data(monkeypatch):
    from totem.devices.network.drivers.bluez import Driver, FIPS_SERVICE_UUID
    from totem.devices.network.models import L2CAPListener, OperationSupport

    listener = L2CAPListener(
        id="listener-1",
        local_address="02:00:00:00:10:01",
        address_type="public",
        psm=0x0081,
        mtu=1024,
        service_uuid=FIPS_SERVICE_UUID,
        advertisement_id=None,
        listening=True,
    )

    class Transport:
        def create_listener(self, **kwargs):
            return listener

        def set_listener_advertisement(self, listener_id, advertisement_id):
            return listener

    driver = Driver(runtime=object())
    driver.initialized = True
    driver._adapter_path = "/org/bluez/hci0"
    driver._l2cap = Transport()
    monkeypatch.setattr(
        driver,
        "get_capabilities",
        lambda: SimpleNamespace(
            address=listener.local_address,
            l2cap=SimpleNamespace(le_coc_listen=OperationSupport(True)),
        ),
    )
    advertisements = []
    monkeypatch.setattr(
        driver,
        "register_advertisement",
        lambda specification, timeout: advertisements.append(specification),
    )

    driver.create_l2cap_listener()

    assert advertisements[0]["service_uuids"] == [FIPS_SERVICE_UUID]
    assert advertisements[0]["service_data"] == {FIPS_SERVICE_UUID: b"\x81\x00"}


def test_bluez_l2cap_listener_rolls_back_when_advertising_fails(monkeypatch):
    from totem.devices.network.drivers.bluez import Driver, FIPS_SERVICE_UUID
    from totem.devices.network.models import L2CAPListener, OperationSupport

    listener = L2CAPListener(
        id="listener-1",
        local_address="02:00:00:00:10:01",
        address_type="public",
        psm=0x0081,
        mtu=1024,
        service_uuid=FIPS_SERVICE_UUID,
        advertisement_id=None,
        listening=True,
    )
    closed = []

    class Transport:
        def create_listener(self, **kwargs):
            return listener

        def close_listener(self, listener_id):
            closed.append(listener_id)

    driver = Driver(runtime=object())
    driver.initialized = True
    driver._adapter_path = "/org/bluez/hci0"
    driver._l2cap = Transport()
    monkeypatch.setattr(
        driver,
        "get_capabilities",
        lambda: SimpleNamespace(
            address=listener.local_address,
            l2cap=SimpleNamespace(le_coc_listen=OperationSupport(True)),
        ),
    )
    monkeypatch.setattr(
        driver,
        "register_advertisement",
        lambda specification, timeout: (_ for _ in ()).throw(
            RadioOperationError("advertising rejected")
        ),
    )

    with pytest.raises(RadioOperationError):
        driver.create_l2cap_listener()

    assert closed == [listener.id]


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
