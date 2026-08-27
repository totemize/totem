"""Radio compatibility routes are bus translators, never network managers."""

from collections.abc import Mapping
from typing import Optional

from fastapi.testclient import TestClient
import pytest

from totem.api.app import create_app
from totem.compat.hardware_client import LegacyHardwareClient, OPERATION_ACTIONS


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class FakeBus:
    def __init__(self, *, failure: Optional[str] = None):
        self.calls = []
        self.failure = failure

    def dispatch(self, message: Mapping[str, object]):
        self.calls.append(dict(message))
        if self.failure:
            return {"type": "{}.result".format(message["type"]), "id": message["id"], "ok": False, "error": {"code": self.failure}}
        value = "scan-1" if message["type"] == "bluetooth.session.discover" else {}
        return {"type": "{}.result".format(message["type"]), "id": message["id"], "ok": True, "value": value}


def make_client(bus=None):
    bus = bus or FakeBus()
    return TestClient(create_app(client=LegacyHardwareClient(bus))), bus


def test_supported_radio_routes_translate_to_provider_owned_actions():
    client, bus = make_client()
    with client:
        assert client.post("/network/configure", json={"ssid": "mesh", "password": "secret", "is_hotspot": True}).status_code == 200
        assert client.post("/network/configure", json={"ssid": "mesh", "password": "secret", "is_hotspot": False}).status_code == 200
        discovery = client.post("/network/bluetooth/discovery", json={"duration_seconds": 20})
        removed = client.post("/network/wifi/p2p/discovery", json={"duration_seconds": 10})

    assert discovery.json() == {"session_id": "scan-1"}
    assert removed.status_code == 501
    assert [call["type"] for call in bus.calls] == ["wifi.connection.hotspot", "wifi.connection.connect", "bluetooth.session.discover"]


@pytest.mark.parametrize("operation,action", sorted(OPERATION_ACTIONS.items()))
def test_operation_table_contains_only_provider_owned_actions(operation, action):
    client, bus = make_client()
    translations = {
        "read_card": (), "write_card": (b"tag",), "read_data": ("note",),
        "write_data": ("note", b"value"), "display_image": (b"frame",),
        "display_bytes": (b"frame",), "display_encoded_image": (b"frame",),
        "scan_wifi_networks": (), "connect_to_network": ("mesh",),
        "disconnect_from_network": (), "create_hotspot": ("mesh",),
        "start_bluetooth_discovery": (),
        "register_bluetooth_advertisement": ({"name": "totem"},),
        "connect_bluetooth_device": ("AA:BB:CC:DD:EE:FF",), "get_ups_status": (),
    }
    with client:
        getattr(client.app.state.hardware_client, operation)(*translations[operation])
    assert bus.calls[-1]["type"] == action
    assert "legacy_call" not in bus.calls[-1]


@pytest.mark.parametrize("code,status", [("unsupported_feature", 501), ("radio_operation_timeout", 504), ("host_unavailable", 503)])
def test_radio_errors_map_to_stable_http_statuses(code, status):
    client, _ = make_client(FakeBus(failure=code))
    with client:
        response = client.post("/network/configure", json={"ssid": "mesh", "password": "secret"})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
