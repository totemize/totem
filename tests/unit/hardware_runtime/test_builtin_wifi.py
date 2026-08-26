"""Built-in Wi-Fi provider tests using injected local seams only."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import pytest

from totem_driver_api import ResourceClaim
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker
from totem.hardware.capabilities.radio.shared import RadioCompatibilityError, RadioCompatibilityPolicy, RadioConstraint
from totem_driver_api.conformance import ConformanceCase, run_host_conformance


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "radio" / "totem-driver-manifest.json"
ENTRY_POINT = "totem.hardware.builtin.radio.wifi_provider:create_provider"
REQUIRED_CLAIMS = (
    ResourceClaim("dbus", "org.freedesktop.NetworkManager"),
    ResourceClaim("interface", "wlan0"),
    ResourceClaim("phy", "phy0"),
)


class _EntryPoint:
    group = "totem.hardware.drivers"
    name = "builtin-wifi"
    value = ENTRY_POINT


class _Distribution:
    metadata = {"Name": "totem", "Version": "0.2.0"}
    entry_points = (_EntryPoint(),)
    files = (Path("totem/hardware/builtin/radio/totem-driver-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/radio/totem-driver-manifest.json"
        return MANIFEST_PATH


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
    return BindingRecord("wifi.connection@1", "wifi", provider_record, REQUIRED_CLAIMS, ())


def _request(request_id: str, message_type: str, **values: object) -> Dict[str, object]:
    return {"type": message_type, "id": request_id, "binding_id": "wifi", **values}


def test_catalog_reads_wifi_manifest_without_importing_network_manager_provider() -> None:
    for name in (
        "totem.hardware.builtin.radio.wifi_provider",
        "totem.hardware.builtin.radio.drivers.network_manager_wifi",
    ):
        importlib.sys.modules.pop(name, None)

    catalog = _catalog()

    assert catalog.diagnostics == ()
    assert catalog.records[0].manifest.factory == ENTRY_POINT
    assert catalog.records[0].manifest.capabilities[0].identifier == "wifi.connection@1"
    assert not any(
        name in importlib.sys.modules
        for name in (
            "totem.hardware.builtin.radio.wifi_provider",
            "totem.hardware.builtin.radio.drivers.network_manager_wifi",
        )
    )


def test_wifi_provider_validates_leased_service_interface_and_phy_before_backend_call() -> None:
    from totem.hardware.builtin.radio.wifi_provider import WiFiProvider, WiFiSelectionError

    calls = []
    provider = WiFiProvider(
        interface="wlan0",
        phy="phy0",
        claims=(ResourceClaim("interface", "wlan0"),),
        runtime=lambda *args: calls.append(args),
    )

    with pytest.raises(WiFiSelectionError, match="claims"):
        provider.session()
    assert calls == []

    selected = WiFiProvider(
        interface="wlan0",
        phy="phy0",
        claims=REQUIRED_CLAIMS,
        runtime=lambda *args: calls.append(args),
    )
    assert selected.session().interface == "wlan0"
    assert calls == []


def test_explicit_mock_session_retains_station_ap_p2p_and_nan_primitives() -> None:
    from totem.hardware.builtin.radio.wifi_provider import WiFiProvider

    provider = WiFiProvider(
        interface="wlan-mock",
        phy="phy-mock",
        explicit_mock=True,
        claims=(
            ResourceClaim("dbus", "org.freedesktop.NetworkManager"),
            ResourceClaim("interface", "wlan-mock"),
            ResourceClaim("phy", "phy-mock"),
        ),
    )
    session = provider.session()
    session.init()

    assert session.get_capabilities().operations["station"].supported
    session.connect("fixture", "")
    session.create_hotspot("fixture-ap", "")
    session.start_p2p_discovery(1)
    assert session.list_p2p_peers()
    discovery = session.start_nan_discovery("totem.fixture", duration_seconds=1)
    assert discovery.id
    session.close()


def test_wifi_has_matching_dual_host_contract_using_mock_session_only(tmp_path: Path) -> None:
    from totem.hardware.builtin.radio.wifi_provider import WiFiProvider

    claim = ResourceBroker().claim(_binding())
    provider = WiFiProvider(
        interface="wlan0", phy="phy0", explicit_mock=True, claims=REQUIRED_CLAIMS
    )
    cases = (
        ConformanceCase("scan", _request("scan", "wifi.connection.scan")),
        ConformanceCase("connect", _request("connect", "wifi.connection.connect", ssid="fixture", password="")),
        ConformanceCase("hotspot", _request("hotspot", "wifi.connection.hotspot", ssid="fixture-ap")),
        ConformanceCase("disconnect", _request("disconnect", "wifi.connection.disconnect")),
        ConformanceCase("unknown", _request("unknown", "wifi.unknown")),
    )
    in_process = run_host_conformance(
        lambda: InProcessDriverHost((claim,), provider, generation=1), cases
    )

    fixture = tmp_path / "wifi_core_fixture.py"
    fixture.write_text(
        "from totem.hardware.builtin.radio.wifi_provider import WiFiProvider\n"
        "from totem_driver_api import ResourceClaim\n"
        "def create_provider():\n"
        "    return WiFiProvider(interface='wlan0', phy='phy0', explicit_mock=True, "
        "claims=(ResourceClaim('dbus', 'org.freedesktop.NetworkManager'), "
        "ResourceClaim('interface', 'wlan0'), ResourceClaim('phy', 'phy0')))\n",
        encoding="utf-8",
    )
    process_claim = ResourceBroker().claim(_binding("wifi_core_fixture:create_provider"))
    process = run_host_conformance(
        lambda: ProcessDriverHost.start(process_claim, site_packages=tmp_path), cases
    )

    assert in_process.items == process.items


def test_wifi_failure_restart_and_shared_phy_denial_are_provider_local() -> None:
    from totem.hardware.builtin.radio.wifi_provider import WiFiProvider, WiFiProviderState

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
    provider = WiFiProvider(
        interface="wlan0", phy="phy0", claims=REQUIRED_CLAIMS,
        driver_factory=lambda: next(candidates),
    )
    with pytest.raises(RuntimeError, match="injected"):
        provider.start()
    assert provider.state is WiFiProviderState.FAILED
    assert provider.restart().initialized is True
    assert provider.state is WiFiProviderState.RUNNING

    def binding(identifier: str, constraint: RadioConstraint) -> BindingRecord:
        return BindingRecord("radio.fixture@1", identifier, SimpleNamespace(), constraint.claims(), ())

    broker = ResourceBroker(compatibility_policy=RadioCompatibilityPolicy())
    broker.claim(binding("hotspot", RadioConstraint("phy0", "wlan0", "wlan0", "wifi.hotspot", "shared")))
    with pytest.raises(RadioCompatibilityError, match="wifi.hotspot"):
        broker.claim(binding("bluetooth", RadioConstraint("phy0", "wlan1", "hci0", "bluetooth.scan", "shared")))
    assert starts == [True, False]
