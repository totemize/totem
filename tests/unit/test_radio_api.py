"""API and event coverage for all radio primitive families."""

import base64

from fastapi.testclient import TestClient
import pytest

from totem.api.app import create_app
from totem.devices.network.errors import RadioTimeoutError, UnsupportedFeatureError
from totem.managers.network_manager import NetworkManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def make_client(manager=None):
    manager = manager or NetworkManager("mock_wifi", allow_mock=True)
    app = create_app({"network": lambda: manager})
    return TestClient(app), manager


def test_capability_status_radio_and_p2p_endpoints():
    client, _ = make_client()
    with client:
        capabilities = client.get("/network/capabilities")
        assert capabilities.status_code == 200
        assert "P2P-GO" in capabilities.json()["wifi"]["interface_modes"]
        assert capabilities.json()["bluetooth"]["roles"] == ["central", "peripheral"]

        assert (
            client.put("/network/wifi/radio", json={"enabled": False}).json()["enabled"]
            is False
        )
        assert (
            client.put("/network/bluetooth/radio", json={"enabled": False}).json()[
                "powered"
            ]
            is False
        )
        assert client.get("/network/wifi/networks").status_code == 200

        assert (
            client.post(
                "/network/wifi/p2p/discovery", json={"duration_seconds": 10}
            ).status_code
            == 200
        )
        peer = client.get("/network/wifi/p2p/peers").json()[0]
        group_response = client.post(
            "/network/wifi/p2p/groups", json={"peer_id": peer["id"]}
        )
        assert group_response.status_code == 200
        group = group_response.json()
        assert group["role"] == "P2P-client"
        assert (
            client.delete("/network/wifi/p2p/groups/{}".format(group["id"])).status_code
            == 200
        )
        assert client.delete("/network/wifi/p2p/discovery").status_code == 200


def test_ble_advertisement_device_and_gatt_endpoints():
    client, _ = make_client()
    with client:
        first = client.post(
            "/network/bluetooth/discovery", json={"duration_seconds": 20}
        ).json()["session_id"]
        second = client.post(
            "/network/bluetooth/discovery", json={"duration_seconds": 20}
        ).json()["session_id"]
        assert (
            client.delete(
                "/network/bluetooth/discovery", params={"session_id": first}
            ).status_code
            == 200
        )
        assert client.get("/network/status").json()["bluetooth_discovery_sessions"] == 1

        advertisement = client.post(
            "/network/bluetooth/advertisements",
            json={
                "local_name": "Totem",
                "service_data_base64": {
                    "12345678-1234-5678-1234-56789abcdef0": base64.b64encode(
                        b"hello"
                    ).decode()
                },
            },
        )
        assert advertisement.status_code == 200
        advertisement_id = advertisement.json()["id"]

        device = client.get("/network/bluetooth/devices").json()[0]
        assert (
            client.post(
                "/network/bluetooth/devices/{}/connect".format(device["id"]), json={}
            ).status_code
            == 200
        )
        service = client.get(
            "/network/bluetooth/devices/{}/gatt".format(device["id"])
        ).json()[0]
        characteristic_id = service["characteristics"][0]["id"]
        path = "/network/bluetooth/devices/{}/gatt/characteristics/{}".format(
            device["id"], characteristic_id
        )
        assert (
            client.put(
                path, json={"value_base64": base64.b64encode(b"written").decode()}
            ).status_code
            == 200
        )
        assert base64.b64decode(client.get(path).json()["value_base64"]) == b"written"
        subscription = client.post(path + "/subscriptions", json={}).json()[
            "subscription_id"
        ]
        assert (
            client.delete(
                "/network/bluetooth/gatt/subscriptions/{}".format(subscription)
            ).status_code
            == 200
        )
        assert (
            client.delete(
                "/network/bluetooth/advertisements/{}".format(advertisement_id)
            ).status_code
            == 200
        )
        assert (
            client.delete(
                "/network/bluetooth/discovery", params={"session_id": second}
            ).status_code
            == 200
        )


def test_radio_errors_map_to_stable_http_statuses():
    class FailingManager:
        def set_event_callback(self, callback):
            pass

        def get_capabilities(self):
            raise UnsupportedFeatureError("not supported")

        def get_status(self):
            raise RadioTimeoutError("timed out")

    client, _ = make_client(FailingManager())
    with client:
        unsupported = client.get("/network/capabilities")
        timeout = client.get("/network/status")

    assert unsupported.status_code == 501
    assert unsupported.json()["detail"]["code"] == "unsupported_feature"
    assert timeout.status_code == 504
    assert timeout.json()["detail"]["code"] == "radio_operation_timeout"


def test_websocket_emits_typed_radio_event():
    client, _ = make_client()
    with client:
        with client.websocket_connect("/ws") as websocket:
            response = client.put("/network/wifi/radio", json={"enabled": False})
            assert response.status_code == 200
            event = websocket.receive_json()

    assert event["device"]["device_type"] == "network"
    assert event["event_type"] == "wifi_radio_state_changed"
    assert event["data"] == {"enabled": False}
