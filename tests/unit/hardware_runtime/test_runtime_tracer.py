"""Claimed fixture binding to process-host and canonical bus tracer tests."""

from __future__ import annotations

import asyncio
import importlib.metadata as metadata
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from totem.hardware.api.app import create_hardware_app
from totem.hardware.api.bus import HardwareBus
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import Resolver
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.hosts.protocol import encode_frame
from totem.hardware.runtime.broker import ResourceBroker


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


ROOT = Path(__file__).parents[3]
API_PACKAGE = ROOT / "packages" / "totem-driver-api"
FIXTURE_PACKAGE = ROOT / "tests" / "fixtures" / "totem-driver-fixture"


def _build_and_install_fixture(tmp_path: Path) -> Path:
    wheels = tmp_path / "wheels"
    site = tmp_path / "site"
    wheels.mkdir()
    for package in (API_PACKAGE, FIXTURE_PACKAGE):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheels),
                str(package),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    for wheel in sorted(wheels.glob("*.whl")):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(site),
                str(wheel),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return site


def _claimed_fixture(site: Path):
    fixture = next(
        distribution
        for distribution in metadata.distributions(path=[str(site)])
        if distribution.metadata["Name"] == "totem-driver-fixture"
    )
    catalog = CatalogScanner(distributions=lambda: (fixture,)).snapshot()
    binding = Resolver().resolve(
        catalog,
        facts=HardwareFacts.from_mapping({"resource.spi": "spi0.0"}),
        capability_id="display.frame-sink@1",
    ).require_binding()
    return ResourceBroker().claim(binding)


def _request(request_id: str, attachment: bytes) -> dict[str, object]:
    return {
        "type": "display.frame.write",
        "id": request_id,
        "binding_id": "fixture.display:display.frame-sink@1",
        "frame": {
            "attachment_id": "frame-1",
            "width": 2,
            "height": 2,
            "pixel_format": "mono1",
        },
        "_attachments": {"frame-1": attachment},
    }


def test_claimed_fixture_binding_starts_child_and_returns_correlated_bus_result(
    tmp_path: Path,
) -> None:
    site = _build_and_install_fixture(tmp_path)
    claim = _claimed_fixture(site)
    os.environ.pop("TOTEM_DRIVER_FIXTURE_IMPORTED", None)
    host = ProcessDriverHost.start(claim, site_packages=site)
    bus = HardwareBus({claim.binding.binding_id: host.display_handle(claim.binding.binding_id)})

    try:
        app = create_hardware_app(bus)

        async def post_bus():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post(
                    "/bus",
                    content=encode_frame(_request("request-1", b"\x00\x01")),
                    headers={"content-type": "application/octet-stream"},
                )

        response = asyncio.run(post_bus())
    finally:
        host.close()

    assert response.status_code == 200
    result = response.json()
    assert result["type"] == "display.frame.write.result"
    assert result["id"] == "request-1"
    assert result["ok"] is True
    assert result["provider_imported"] is True
    assert os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") is None


def test_concurrent_generic_bus_dispatch_and_safe_errors_use_binding_table(tmp_path: Path) -> None:
    site = _build_and_install_fixture(tmp_path)
    claim = _claimed_fixture(site)
    host = ProcessDriverHost.start(claim, site_packages=site)
    bus = HardwareBus({claim.binding.binding_id: host.display_handle(claim.binding.binding_id)})

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda index: bus.dispatch(_request("request-{}".format(index), bytes([index]))),
                    range(16),
                )
            )
        unknown = bus.dispatch({"type": "display.unknown", "id": "bad-1"})
    finally:
        host.close()

    assert {result["id"] for result in results} == {
        "request-{}".format(index) for index in range(16)
    }
    assert all(result["type"] == "display.frame.write.result" for result in results)
    assert unknown == {
        "type": "display.unknown.result",
        "id": "bad-1",
        "ok": False,
        "error": {"code": "unknown_type", "message": "unknown message type"},
    }
    assert "router" not in repr(bus).lower()
    assert "traceback" not in repr(unknown).lower()
