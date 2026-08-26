"""Compatibility API facades remain outward translators over the canonical bus."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping

import httpx
import pytest

from totem.api.app import LEGACY_ROUTE_ACTIONS, create_app
from totem.compat.hardware_client import LegacyHardwareClient
from totem.compat.hardware_env import legacy_runtime_config


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class _Bus:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def dispatch(self, message: Mapping[str, object]) -> dict[str, object]:
        call = dict(message)
        self.calls.append(call)
        return {
            "type": "{}.result".format(message["type"]),
            "id": message["id"],
            "ok": True,
            "value": {"data": b"\x00\xff"},
        }


async def _call(app, method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_legacy_client_dispatches_one_canonical_action_with_raw_attachments() -> None:
    bus = _Bus()
    client = LegacyHardwareClient(bus)

    result = client.call(
        "display.frame.write",
        {"width": 2, "height": 2},
        attachments={"frame": b"\x00\x01"},
    )

    assert result["ok"] is True
    assert bus.calls == [
        {
            "type": "display.frame.write",
            "id": "legacy-1",
            "width": 2,
            "height": 2,
            "_attachments": {"frame": b"\x00\x01"},
        }
    ]


def test_display_base64_is_decoded_only_at_legacy_edge() -> None:
    bus = _Bus()
    app = create_app(client=LegacyHardwareClient(bus))
    response = asyncio.run(
        _call(
            app,
            "post",
            "/display/image",
            json={"image_base64": base64.b64encode(b"frame").decode("ascii")},
        )
    )

    assert response.status_code == 200
    assert bus.calls[0]["type"] == "display.frame.write"
    assert bus.calls[0]["_attachments"] == {"frame": b"frame"}


def test_route_inventory_has_a_canonical_action_for_every_legacy_hardware_route() -> None:
    app = create_app(client=LegacyHardwareClient(_Bus()))
    routes = {
        (next(iter(route.methods)), route.path)
        for route in app.routes
        if getattr(route, "path", "")
        not in {"/", "/health", "/ws", "/bus", "/bus/events", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
        and getattr(route, "methods", None)
    }

    assert routes == set(LEGACY_ROUTE_ACTIONS)
    assert all(action for action in LEGACY_ROUTE_ACTIONS.values())


def test_legacy_environment_is_typed_at_the_compatibility_boundary(monkeypatch) -> None:
    monkeypatch.setenv("TOTEM_ALLOW_MOCK_DRIVERS", "true")
    monkeypatch.setenv("TOTEM_STORAGE_ROOT", "/tmp/totem-storage")

    config = legacy_runtime_config()

    assert config.allow_mock_drivers is True
    assert config.storage_root == "/tmp/totem-storage"
