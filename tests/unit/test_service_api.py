"""Legacy service routes project canonical bus requests and results."""

import asyncio
import base64
from collections.abc import Mapping

from fastapi.testclient import TestClient
import pytest

from totem.api.app import create_app
from totem.api.event_manager import EventManager
from totem.compat.hardware_client import LegacyHardwareClient
from totem.hardware.runtime.events import RuntimeEventStream


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class FakeBus:
    def __init__(self):
        self.calls = []

    def dispatch(self, message: Mapping[str, object]):
        call = dict(message)
        self.calls.append(call)
        values = {
            "nfc.tag.read": "totem-tag",
            "storage.files.read": b"\x00\xff",
            "power.telemetry.read": {
                "model": "PiSugar 2",
                "battery_percent": 73.5,
                "voltage_volts": 3.91,
                "current_amps": -0.18,
                "power_plugged": False,
            },
        }
        return {"type": "{}.result".format(message["type"]), "id": message["id"], "ok": True, "value": values.get(message["type"], {})}


def make_client():
    bus = FakeBus()
    return TestClient(create_app(client=LegacyHardwareClient(bus))), bus


def test_api_translates_legacy_service_shapes_to_canonical_bus_requests():
    client, bus = make_client()
    with client:
        text = client.post("/display/text", json={"text": "hello", "font_size": 18, "x": 4, "y": 9})
        assert text.status_code == 501
        assert text.json()["detail"]["code"] == "unsupported_feature"
        assert client.post("/display/image", json={"image_base64": base64.b64encode(b"image").decode("ascii")}).status_code == 200
        assert client.post("/nfc/write", json={"data": "payload"}).status_code == 200
        assert "totem-tag" in client.post("/nfc/read").json()["message"]
        assert client.post("/storage/write", json={"path": "new.bin", "data_base64": base64.b64encode(b"stored").decode("ascii")}).status_code == 200
        assert client.post("/network/configure", json={"ssid": "mesh", "password": "secret", "is_hotspot": True}).status_code == 200
        assert client.post("/network/configure", json={"ssid": "wifi", "password": "secret", "is_hotspot": False}).status_code == 200
        assert client.get("/ups/status").json() == {
            "model": "PiSugar 2", "battery_percent": 73.5, "voltage_volts": 3.91,
            "current_amps": -0.18, "power_plugged": False,
        }

    actions = [call["type"] for call in bus.calls]
    assert actions == [
        "display.frame.write", "nfc.tag.write", "nfc.tag.read",
        "storage.files.write", "wifi.connection.hotspot", "wifi.connection.connect",
        "power.telemetry.read",
    ]
    assert bus.calls[0]["_attachments"] == {"frame": b"image"}
    assert base64.b64decode(bus.calls[3]["data_b64"]) == b"stored"


def test_storage_read_returns_binary_as_base64():
    client, _ = make_client()
    with client:
        response = client.post("/storage/read", json={"path": "existing.bin"})

    assert response.status_code == 200
    assert base64.b64decode(response.json()["data_base64"]) == b"\x00\xff"


def test_binary_endpoints_reject_invalid_or_unbounded_base64():
    client, _ = make_client()
    with client:
        image = client.post("/display/image", json={"image_base64": "***"})
        storage = client.post("/storage/write", json={"path": "file.bin", "data_base64": "***"})

    assert image.status_code == 422
    assert storage.status_code == 422


def test_canonical_host_unavailability_is_a_stable_503():
    with TestClient(create_app(client=LegacyHardwareClient())) as client:
        response = client.post("/nfc/read")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "host_unavailable"


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


def test_event_manager_projects_the_injected_runtime_event_stream_without_a_manager_queue():
    class FakeWebSocket:
        def __init__(self):
            self.messages = []

        async def accept(self):
            pass

        async def send_text(self, value):
            self.messages.append(value)

    async def exercise():
        events = RuntimeEventStream()
        manager = EventManager(events)
        websocket = FakeWebSocket()
        await manager.start()
        await asyncio.sleep(0.01)
        await manager.connect(websocket)
        events.publish("radio-wifi", "starting", "ready", code="ready")
        for _ in range(50):
            if websocket.messages:
                break
            await asyncio.sleep(0.01)
        await manager.shutdown()
        return websocket.messages

    messages = asyncio.run(exercise())
    assert '"event_type":"hardware_event"' in messages[0]
    assert '"binding_id":"radio-wifi"' in messages[0]
