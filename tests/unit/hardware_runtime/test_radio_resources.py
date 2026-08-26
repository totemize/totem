"""Fixture-only radio contracts and deterministic coexistence tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest

from totem.hardware.capabilities.radio.shared import (
    RadioCompatibilityError,
    RadioCompatibilityPolicy,
    RadioConstraint,
)
from totem.hardware.catalog.metadata import CatalogRecord
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker
from totem_driver_api.capabilities.radio.bluetooth import (
    BLUETOOTH_SESSION,
    BluetoothAdvertisementRequest,
    BluetoothDevice,
    BluetoothDiscoverRequest,
    BluetoothDiscoveryResult,
)
from totem_driver_api.capabilities.radio.wifi import (
    WIFI_CONNECTION,
    WifiConnectRequest,
    WifiNetwork,
    WifiScanRequest,
    WifiScanResult,
)


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def _binding(name: str, constraint: RadioConstraint) -> BindingRecord:
    return BindingRecord(
        capability_id="radio.fixture@1",
        binding_id=name,
        provider_record=cast(CatalogRecord, object()),
        claims=constraint.claims(),
        config=(),
    )


def test_public_wifi_and_bluetooth_contracts_are_narrow_and_json_data_only() -> None:
    wifi = WifiScanResult((WifiNetwork(ssid="!Totem", signal_dbm=-42, secure=False),))
    bluetooth = BluetoothDiscoveryResult((BluetoothDevice(address="AA:BB:CC:DD:EE:FF", name="Totem"),))

    assert WIFI_CONNECTION.value == "wifi.connection@1"
    assert BLUETOOTH_SESSION.value == "bluetooth.session@1"
    assert WifiScanRequest().to_json_value() == {}
    assert WifiConnectRequest("!Totem", password="test").to_json_value() == {
        "ssid": "!Totem",
        "password": "test",
    }
    assert wifi.to_json_value() == {"networks": [{"ssid": "!Totem", "signal_dbm": -42, "secure": False}]}
    assert BluetoothDiscoverRequest().to_json_value() == {}
    assert BluetoothAdvertisementRequest("Totem").to_json_value() == {"name": "Totem"}
    assert bluetooth.to_json_value() == {
        "devices": [{"address": "AA:BB:CC:DD:EE:FF", "name": "Totem"}]
    }


def test_radio_constraints_express_generic_claims_and_a_stable_operation_mode() -> None:
    constraint = RadioConstraint(
        phy="phy0",
        interface="wlan0",
        adapter="hci0",
        mode="wifi.station",
        compatibility_group="shared-radio",
    )

    assert tuple((claim.kind, claim.identifier, claim.exclusive, claim.group) for claim in constraint.claims()) == (
        ("phy", "phy0", False, "shared-radio"),
        ("interface", "wlan0", False, "shared-radio"),
        ("adapter", "hci0", False, "shared-radio"),
        ("compatibility", "wifi.station", False, "shared-radio"),
    )


@pytest.mark.parametrize(
    ("left", "right", "allowed"),
    (
        ("wifi.station", "wifi.station", True),
        ("wifi.station", "bluetooth.scan", True),
        ("wifi.station", "bluetooth.advertise", True),
        ("wifi.hotspot", "wifi.station", False),
        ("wifi.hotspot", "bluetooth.scan", False),
        ("wifi.hotspot", "bluetooth.advertise", False),
        ("bluetooth.scan", "bluetooth.advertise", True),
    ),
)
def test_radio_compatibility_matrix_is_explicit_symmetric_and_exhaustive(
    left: str, right: str, allowed: bool
) -> None:
    policy = RadioCompatibilityPolicy()
    first = RadioConstraint("phy0", "wlan0", "hci0", left, "shared-radio")
    second = RadioConstraint("phy0", "wlan1", "hci1", right, "shared-radio")

    assert policy.permits(first, second) is allowed
    assert policy.permits(second, first) is allowed


def test_broker_rejects_incompatible_shared_phy_modes_and_preserves_existing_owner() -> None:
    broker = ResourceBroker(compatibility_policy=RadioCompatibilityPolicy())
    first = broker.acquire(_binding("wifi", RadioConstraint("phy0", "wlan0", "hci0", "wifi.hotspot", "shared-radio")))

    with pytest.raises(RadioCompatibilityError, match="wifi.hotspot"):
        broker.acquire(_binding("bluetooth", RadioConstraint("phy0", "wlan1", "hci1", "bluetooth.scan", "shared-radio")))

    assert broker.snapshot()[0]["binding_id"] == first.binding_id


def test_shuffled_permitted_and_denied_claims_are_deterministic_without_a_global_radio_lock() -> None:
    policy = RadioCompatibilityPolicy()

    def acquire(index: int) -> str:
        broker = ResourceBroker(compatibility_policy=policy)
        station = _binding("station", RadioConstraint("phy0", "wlan0", "hci0", "wifi.station", "shared-radio"))
        scan = _binding("scan", RadioConstraint("phy0", "wlan1", "hci1", "bluetooth.scan", "shared-radio"))
        hotspot = _binding("hotspot", RadioConstraint("phy0", "wlan2", "hci2", "wifi.hotspot", "shared-radio"))
        ordered = (station, scan, hotspot) if index % 2 else (hotspot, scan, station)
        result: list[str] = []
        for binding in ordered:
            try:
                broker.acquire(binding)
            except RadioCompatibilityError:
                result.append("denied:" + binding.binding_id)
            else:
                result.append("granted:" + binding.binding_id)
        return ",".join(sorted(result))

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = set(pool.map(acquire, range(32)))

    assert outcomes == {
        "denied:hotspot,granted:scan,granted:station",
        "denied:scan,denied:station,granted:hotspot",
    }


def test_independent_phys_are_permitted_concurrently() -> None:
    broker = ResourceBroker(compatibility_policy=RadioCompatibilityPolicy())
    bindings = (
        _binding("left", RadioConstraint("phy0", "wlan0", "hci0", "wifi.hotspot", "shared-radio")),
        _binding("right", RadioConstraint("phy1", "wlan1", "hci1", "bluetooth.scan", "shared-radio")),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        leases = tuple(pool.map(broker.acquire, bindings))

    assert {lease.binding_id for lease in leases} == {"left", "right"}
