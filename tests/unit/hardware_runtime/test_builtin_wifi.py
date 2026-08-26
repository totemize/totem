"""Built-in Wi-Fi provider tests using injected local seams only."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from totem_driver_api import ResourceClaim
from totem.hardware.catalog.metadata import CatalogScanner


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
MANIFEST_PATH = ROOT / "src" / "totem" / "hardware" / "builtin" / "radio" / "wifi-manifest.json"
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
    files = (Path("totem/hardware/builtin/radio/wifi-manifest.json"),)

    def locate_file(self, path: Path) -> Path:
        assert str(path) == "totem/hardware/builtin/radio/wifi-manifest.json"
        return MANIFEST_PATH


def test_catalog_reads_wifi_manifest_without_importing_network_manager_provider() -> None:
    for name in (
        "totem.hardware.builtin.radio.wifi_provider",
        "totem.hardware.builtin.radio.drivers.network_manager_wifi",
    ):
        importlib.sys.modules.pop(name, None)

    catalog = CatalogScanner(distributions=lambda: (_Distribution(),)).snapshot()

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
