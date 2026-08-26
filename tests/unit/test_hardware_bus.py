"""Local ASGI coverage for the runtime-owned hardware bus facade."""

from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace
from typing import Mapping

import httpx
import pytest

from totem.hardware.api.app import create_hardware_app
from totem.hardware.api.bus import HardwareBus
from totem.hardware.hosts.protocol import encode_frame
from totem.hardware.runtime.events import RuntimeEventStream


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class _Handle:
    def __init__(self, binding_id: str) -> None:
        self.binding_id = binding_id
        self.calls: list[dict[str, object]] = []

    def dispatch(self, message: Mapping[str, object]) -> dict[str, object]:
        self.calls.append(dict(message))
        if message["type"] == "display.unknown":
            return {
                "type": "display.unknown.result",
                "id": message["id"],
                "ok": False,
                "error": {"code": "unknown_type", "message": "unknown message type"},
            }
        return {
            "type": "{}.result".format(message["type"]),
            "id": message["id"],
            "ok": True,
            "binding_id": self.binding_id,
        }


class _Runtime:
    def __init__(self) -> None:
        self.events = RuntimeEventStream(queue_size=1)
        self.bindings = MappingProxyType(
            {"display": SimpleNamespace(capability_id="display.frame-sink@1")}
        )
        self.handle_value = _Handle("display")
        self.started = 0
        self.closed = 0

    def start(self) -> object:
        self.started += 1
        return self.health()

    def close(self) -> object:
        self.closed += 1
        return self.health()

    def health(self) -> object:
        return SimpleNamespace(
            ready=True,
            degraded=False,
            closed=bool(self.closed),
            state=SimpleNamespace(value="ready"),
            bindings=MappingProxyType(
                {
                    "display": SimpleNamespace(
                        binding_id="display",
                        capability_id="display.frame-sink@1",
                        required=True,
                        state="ready",
                        generation=1,
                        quarantined=False,
                        contaminated=False,
                    )
                }
            ),
        )

    def handle(self, capability_id: str, binding_id: str) -> _Handle:
        assert capability_id == "display.frame-sink@1"
        assert binding_id == "display"
        return self.handle_value


def _request(request_id: str = "request-1") -> dict[str, object]:
    return {
        "type": "display.frame.write",
        "id": request_id,
        "binding_id": "display",
        "frame": {"attachment_id": "frame-1", "width": 2, "height": 2, "pixel_format": "mono1"},
        "_attachments": {"frame-1": b"\x00\x01"},
    }


async def _call(app, method: str, path: str, *, client: tuple[str, int], **kwargs):
    transport = httpx.ASGITransport(app=app, client=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        return await http.request(method, path, **kwargs)


def test_bus_correlates_requests_rejects_unknown_pushes_and_bounds_attachments() -> None:
    runtime = _Runtime()
    bus = HardwareBus(runtime)

    result = bus.dispatch(_request())
    unknown = bus.dispatch({"type": "display.unknown", "id": "unknown-1", "binding_id": "display"})
    push = bus.dispatch({"type": "display.unknown", "binding_id": "display"})
    oversized = bus.dispatch(
        {
            "type": "display.frame.write",
            "id": "large-1",
            "binding_id": "display",
            "_attachments": {"frame-1": b"x" * (16 * 1024 * 1024 + 1)},
        }
    )

    assert result == {
        "type": "display.frame.write.result",
        "id": "request-1",
        "ok": True,
        "binding_id": "display",
    }
    assert unknown["type"] == "display.unknown.result"
    assert unknown["id"] == "unknown-1"
    assert unknown["error"]["code"] == "unknown_type"
    assert push is None
    assert oversized["id"] == "large-1"
    assert oversized["error"]["code"] == "attachment_too_large"


def test_bus_projects_redacted_hardware_status_through_canonical_result() -> None:
    result = HardwareBus(_Runtime()).dispatch(
        {"type": "hardware.status.get", "id": "health-1"}
    )

    assert result == {
        "type": "hardware.status.get.result",
        "id": "health-1",
        "ok": True,
        "status": {"ready": True, "degraded": False},
    }


def test_app_lifespan_uses_one_injected_runtime_and_rejects_spoofed_peers() -> None:
    runtime = _Runtime()
    app = create_hardware_app(runtime=runtime)

    async def lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert runtime.started == 1
            accepted = await _call(
                app,
                "post",
                "/bus",
                client=("127.0.0.1", 4455),
                content=encode_frame(_request()),
                headers={"content-type": "application/octet-stream", "x-forwarded-for": "203.0.113.1"},
            )
            assert accepted.status_code == 200
            assert accepted.json()["id"] == "request-1"
            assert (await _call(app, "get", "/health", client=("127.0.0.1", 4455))).json()["ready"] is True
            for path in ("/bus", "/bus/events", "/health"):
                response = await _call(
                    app,
                    "post" if path == "/bus" else "get",
                    path,
                    client=("198.51.100.8", 4455),
                    content=encode_frame(_request()) if path == "/bus" else None,
                    headers={"content-type": "application/octet-stream", "x-forwarded-for": "127.0.0.1"},
                )
                assert response.status_code == 403

    asyncio.run(lifespan())
    assert runtime.started == 1
    assert runtime.closed == 1


def test_sse_projection_is_typed_ordered_lossy_and_redacted() -> None:
    runtime = _Runtime()
    app = create_hardware_app(runtime=runtime)
    slow_subscriber = runtime.events.subscribe()

    runtime.events.publish("display", "starting", "ready", details={"token": "secret", "safe": "one"})
    runtime.events.publish("display", "ready", "failed", code="child_exit", details={"traceback": "private", "safe": "two"})

    projection = app.state.hardware_events.project_history()

    assert [event["sequence"] for event in projection] == [1, 2]
    assert all(event["type"] == "hardware.lifecycle" for event in projection)
    assert projection[0]["details"] == {"safe": "one"}
    assert projection[1]["details"] == {"safe": "two"}
    assert "secret" not in repr(projection)
    assert "private" not in repr(projection)
    assert runtime.events.dropped_events == 1
    assert slow_subscriber.get_nowait().sequence == 2
    assert app.state.hardware_events.dropped_events == 1
