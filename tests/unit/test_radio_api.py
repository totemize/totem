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
        value = "scan-1" if message["type"] == "radio.bluetooth.discovery.create" else {}
        return {"type": "{}.result".format(message["type"]), "id": message["id"], "ok": True, "value": value}


def make_client(bus=None):
    bus = bus or FakeBus()
    return TestClient(create_app(client=LegacyHardwareClient(bus))), bus


def test_radio_status_routes_translate_to_independent_canonical_actions():
    client, bus = make_client()
    with client:
        assert client.post("/network/configure", json={"ssid": "mesh", "password": "secret", "is_hotspot": True}).status_code == 200
        assert client.post("/network/configure", json={"ssid": "mesh", "password": "secret", "is_hotspot": False}).status_code == 200
        assert client.post("/network/wifi/p2p/discovery", json={"duration_seconds": 10}).status_code == 200
        discovery = client.post("/network/bluetooth/discovery", json={"duration_seconds": 20})

    assert discovery.json() == {"session_id": "scan-1"}
    assert [call["type"] for call in bus.calls] == [
        "radio.wifi.hotspot.create", "radio.wifi.connection.create",
        "radio.wifi.p2p.discovery.create", "radio.bluetooth.discovery.create",
    ]


def test_radio_operation_table_covers_every_deployed_radio_family():
    actions = set(OPERATION_ACTIONS.values())
    assert any(action.startswith("radio.wifi.") for action in actions)
    assert any(action.startswith("radio.bluetooth.") for action in actions)
    assert {"radio.wifi.p2p.discovery.create", "radio.wifi.aware.discovery.create", "radio.bluetooth.gatt.characteristics.write", "radio.bluetooth.l2cap.connections.handoff"} <= actions


@pytest.mark.parametrize("code,status", [("unsupported_feature", 501), ("radio_operation_timeout", 504), ("host_unavailable", 503)])
def test_radio_errors_map_to_stable_http_statuses(code, status):
    client, _ = make_client(FakeBus(failure=code))
    with client:
        response = client.post("/network/configure", json={"ssid": "mesh", "password": "secret"})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
