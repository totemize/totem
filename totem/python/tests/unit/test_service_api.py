import asyncio
import base64

from fastapi.testclient import TestClient
import pytest

from service.event_manager import EventManager
from service.main import create_app


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class FakeDisplayManager:
    def __init__(self):
        self.text_calls = []
        self.image_calls = []

    def display_text(self, text, font_size, x, y):
        self.text_calls.append((text, font_size, x, y))

    def display_bytes(self, data):
        self.image_calls.append(data)


class FakeNFCManager:
    def __init__(self):
        self.writes = []

    def read_card(self):
        return "totem-tag"

    def write_card(self, data):
        self.writes.append(data)


class FakeStorageManager:
    def __init__(self):
        self.files = {"existing.bin": b"\x00\xff"}

    def read_data(self, path):
        return self.files[path]

    def write_data(self, path, data):
        self.files[path] = data
        return True


class FakeNetworkManager:
    def __init__(self):
        self.connections = []
        self.hotspots = []

    def connect_to_network(self, ssid, password):
        self.connections.append((ssid, password))

    def create_hotspot(self, ssid, password):
        self.hotspots.append((ssid, password))


def make_client():
    managers = {
        "display": FakeDisplayManager(),
        "nfc": FakeNFCManager(),
        "storage": FakeStorageManager(),
        "network": FakeNetworkManager(),
    }
    app = create_app({name: lambda value=value: value for name, value in managers.items()})
    return TestClient(app), managers


def test_api_calls_synchronous_manager_contracts():
    client, managers = make_client()
    with client:
        response = client.post(
            "/display/text",
            json={"text": "hello", "font_size": 18, "position": {"x": 4, "y": 9}},
        )
        assert response.status_code == 200
        assert managers["display"].text_calls == [("hello", 18, 4, 9)]

        response = client.post("/display/image", json={"image_data": "image"})
        assert response.status_code == 200
        assert managers["display"].image_calls == [b"image"]

        response = client.post("/nfc/write", json={"data": "payload"})
        assert response.status_code == 200
        assert managers["nfc"].writes == ["payload"]

        response = client.post("/nfc/read")
        assert response.status_code == 200
        assert "totem-tag" in response.json()["message"]

        response = client.post(
            "/storage/write", json={"path": "new.bin", "data": "stored"}
        )
        assert response.status_code == 200
        assert managers["storage"].files["new.bin"] == b"stored"

        response = client.post(
            "/network/configure",
            json={"ssid": "mesh", "password": "secret", "is_hotspot": True},
        )
        assert response.status_code == 200
        assert managers["network"].hotspots == [("mesh", "secret")]

        response = client.post(
            "/network/configure",
            json={"ssid": "wifi", "password": "secret", "is_hotspot": False},
        )
        assert response.status_code == 200
        assert managers["network"].connections == [("wifi", "secret")]


def test_storage_read_returns_binary_as_base64():
    client, _ = make_client()
    with client:
        response = client.post("/storage/read", json={"path": "existing.bin"})

    assert response.status_code == 200
    assert base64.b64decode(response.json()["data_base64"]) == b"\x00\xff"


def test_manager_initialization_is_lazy_and_failure_is_503():
    calls = []

    def unavailable():
        calls.append("nfc")
        raise RuntimeError("not connected")

    app = create_app({"nfc": unavailable})
    with TestClient(app) as client:
        assert calls == []
        response = client.post("/nfc/read")

    assert calls == ["nfc"]
    assert response.status_code == 503
    assert response.json()["detail"] == "Nfc hardware is unavailable"


def test_event_manager_requires_explicit_lifecycle_and_accepts_once():
    class FakeWebSocket:
        def __init__(self):
            self.accept_count = 0

        async def accept(self):
            self.accept_count += 1

    async def exercise():
        manager = EventManager()
        websocket = FakeWebSocket()
        assert manager.processor_task is None
        await manager.start()
        await manager.connect(websocket)
        await manager.disconnect(websocket)
        await manager.disconnect(websocket)
        await manager.shutdown()
        assert manager.processor_task is None
        return websocket.accept_count

    assert asyncio.run(exercise()) == 1
