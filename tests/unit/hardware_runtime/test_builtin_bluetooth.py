"""Built-in Bluetooth provider tests using injected local seams only."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import pytest

from totem_driver_api import ResourceClaim
from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.capabilities.radio.shared import (
    RadioCompatibilityError,
    RadioCompatibilityPolicy,
    RadioConstraint,
)
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "radio" / "bluetooth-manifest.json"
WIFI_MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "radio" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.radio.bluetooth_provider:create_provider"
REQUIRED_CLAIMS = (
    ResourceClaim("dbus", "org.bluez"),
    ResourceClaim("interface", "hci0"),
    ResourceClaim("phy", "phy0"),
)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-bluetooth"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)
    files = (
        Path("totem/hardware/builtin/radio/totem-driver-manifest.json"),
        Path("totem/hardware/builtin/radio/bluetooth-manifest.json"),
    )

    def locate_file(self, path: Path) -> Path:
        if str(path) == "totem/hardware/builtin/radio/bluetooth-manifest.json":
            return MANIFEST_PATH
        assert str(path) == "totem/hardware/builtin/radio/totem-driver-manifest.json"
        return WIFI_MANIFEST_PATH


def _catalog():
    return CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()


def _binding(entry_point: str = ENTRY_POINT) -> BindingRecord:
    record = _catalog().records[0]
    provider_record = SimpleNamespace(
        entry_point_value=entry_point,
        provider_id=record.provider_id,
        distribution_version="0.2.0",
        manifest=record.manifest,
    )
    return BindingRecord("bluetooth.session@1", "bluetooth", provider_record, REQUIRED_CLAIMS, ())


def _request(request_id: str, message_type: str, **values: object) -> Dict[str, object]:
    return {"type": message_type, "id": request_id, "binding_id": "bluetooth", **values}


def test_catalog_reads_bluetooth_manifest_without_importing_bluez_provider() -> None:
    for name in (
        "totem.hardware.builtin.radio.bluetooth_provider",
        "totem.hardware.builtin.radio.drivers.bluez",
    ):
        importlib.sys.modules.pop(name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert catalog.records[0].manifest.capabilities[0].identifier == "bluetooth.session@1"
    assert not any(
        name in importlib.sys.modules
        for name in (
            "totem.hardware.builtin.radio.bluetooth_provider",
            "totem.hardware.builtin.radio.drivers.bluez",
        )
    )


def test_bluetooth_provider_validates_leased_service_adapter_and_phy_before_backend_call() -> None:
    from totem.hardware.builtin.radio.bluetooth_provider import (
        BluetoothProvider,
        BluetoothSelectionError,
    )

    calls = []
    provider = BluetoothProvider(
        adapter="hci0",
        phy="phy0",
        claims=(ResourceClaim("interface", "hci0"),),
        runtime=lambda *args: calls.append(args),
    )

    with pytest.raises(BluetoothSelectionError, match="claims"):
        provider.session()
    assert calls == []

    selected = BluetoothProvider(
        adapter="hci0",
        phy="phy0",
        claims=REQUIRED_CLAIMS,
        runtime=lambda *args: calls.append(args),
    )
    assert selected.session()._runtime is selected._runtime
    assert calls == []


def test_explicit_mock_session_retains_radio_discovery_advertising_gatt_and_l2cap() -> None:
    from totem.hardware.builtin.radio.bluetooth_provider import BluetoothProvider

    provider = BluetoothProvider(
        adapter="hci-mock",
        phy="phy-mock",
        explicit_mock=True,
        claims=(
            ResourceClaim("dbus", "org.bluez"),
            ResourceClaim("interface", "hci-mock"),
            ResourceClaim("phy", "phy-mock"),
        ),
    )
    session = provider.session()
    session.init()

    assert session.get_capabilities().operations["gatt_client"].supported
    discovery_id = session.start_discovery(duration_seconds=1)
    device = session.list_devices()[0]
    advertisement = session.register_advertisement({"local_name": "fixture"})
    session.connect_device(device.id)
    characteristic = session.list_gatt(device.id)[0].characteristics[0]
    session.write_characteristic(device.id, characteristic.id, b"fixture")
    assert session.read_characteristic(device.id, characteristic.id) == b"fixture"
    listener = session.create_l2cap_listener("12345678-1234-5678-1234-56789abcdef0")
    connection = session.connect_l2cap(device.address, listener.psm)
    assert connection.id
    session.close_l2cap_connection(connection.id)
    session.close_l2cap_listener(listener.id)
    session.unregister_advertisement(advertisement.id)
    session.stop_discovery(discovery_id)
    session.close()


def test_bluetooth_has_matching_dual_host_contract_using_mock_session_only(tmp_path: Path) -> None:
    from totem.hardware.builtin.radio.bluetooth_provider import BluetoothProvider

    claim = ResourceBroker().claim(_binding())
    provider = BluetoothProvider(
        adapter="hci0", phy="phy0", explicit_mock=True, claims=REQUIRED_CLAIMS
    )
    cases = (
        ConformanceCase("discover", _request("discover", "bluetooth.session.discover")),
        ConformanceCase("advertise", _request("advertise", "bluetooth.session.advertise", name="fixture")),
        ConformanceCase("connect", _request("connect", "bluetooth.session.connect", address="02:00:00:00:10:02")),
        ConformanceCase("unknown", _request("unknown", "bluetooth.unknown")),
    )
    in_process = run_host_conformance(
        lambda: InProcessDriverHost((claim,), provider, generation=1), cases
    )

    fixture = tmp_path / "bluetooth_core_fixture.py"
    fixture.write_text(
        "from totem.hardware.builtin.radio.bluetooth_provider import BluetoothProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "def create_provider():\n"
        "    return BluetoothProvider(adapter='hci0', phy='phy0', explicit_mock=True, "
        "claims=(ResourceClaim('dbus', 'org.bluez'), ResourceClaim('interface', 'hci0'), "
        "ResourceClaim('phy', 'phy0')))\n",
        encoding="utf-8",
    )
    process_claim = ResourceBroker().claim(_binding("bluetooth_core_fixture:create_provider"))
    process = run_host_conformance(
        lambda: ProcessDriverHost.start(process_claim, site_packages=tmp_path), cases
    )

    assert in_process.items == process.items


def test_bluetooth_failure_restart_and_shared_phy_denial_are_provider_local() -> None:
    from totem.hardware.builtin.radio.bluetooth_provider import (
        BluetoothProvider,
        BluetoothProviderState,
    )

    starts = []

    class _Session:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.initialized = False

        def init(self) -> None:
            starts.append(self.fail)
            if self.fail:
                raise RuntimeError("injected failure")
            self.initialized = True

        def close(self) -> None:
            return None

    candidates = iter((_Session(True), _Session(False)))
    provider = BluetoothProvider(
        adapter="hci0", phy="phy0", claims=REQUIRED_CLAIMS,
        driver_factory=lambda: next(candidates),
    )
    with pytest.raises(RuntimeError, match="injected"):
        provider.start()
    assert provider.state is BluetoothProviderState.FAILED
    assert provider.restart().initialized is True
    assert provider.state is BluetoothProviderState.RUNNING

    def binding(identifier: str, constraint: RadioConstraint) -> BindingRecord:
        return BindingRecord("radio.fixture@1", identifier, SimpleNamespace(), constraint.claims(), ())

    broker = ResourceBroker(compatibility_policy=RadioCompatibilityPolicy())
    broker.claim(binding("hotspot", RadioConstraint("phy0", "wlan0", "wlan0", "wifi.hotspot", "shared")))
    with pytest.raises(RadioCompatibilityError, match="wifi.hotspot"):
        broker.claim(binding("bluetooth", RadioConstraint("phy0", "hci0", "hci0", "bluetooth.scan", "shared")))
    assert starts == [True, False]


def test_legacy_bluetooth_modules_reexport_canonical_implementations() -> None:
    from totem.devices.network.drivers.bluez import Driver as LegacyBlueZ
    from totem.devices.network.drivers.mock_bluetooth import Driver as LegacyMockBluetooth
    from totem.devices.network.l2cap import L2CAPTransport as LegacyL2CAP
    from totem.hardware.builtin.radio.drivers.bluez import Driver as CanonicalBlueZ
    from totem.hardware.builtin.radio.drivers.mock_bluetooth import Driver as CanonicalMockBluetooth
    from totem.hardware.builtin.radio.l2cap import L2CAPTransport as CanonicalL2CAP

    assert LegacyBlueZ is CanonicalBlueZ
    assert LegacyMockBluetooth is CanonicalMockBluetooth
    assert LegacyL2CAP is CanonicalL2CAP
