"""Public conformance helpers exercise the same ordered contract in both hosts."""

from __future__ import annotations

import os
import importlib.metadata as metadata
from pathlib import Path
import subprocess
import sys
from typing import Dict

import pytest

from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.hosts.process import ProcessDriverHost
from totem.hardware.catalog.metadata import CatalogScanner
from totem.hardware.discovery.facts import HardwareFacts
from totem.hardware.discovery.resolver import Resolver
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]

ROOT = Path(__file__).parents[3]
API_PACKAGE = ROOT / "packages" / "totem-driver-api"
FIXTURE_PACKAGE = ROOT / "tests" / "fixtures" / "totem-driver-fixture"


def _binding() -> BindingRecord:
    from types import SimpleNamespace

    record = SimpleNamespace(
        provider_id="fixture.display",
        distribution_version="1.0.0",
        entry_point_value="fixture:provider",
        manifest=SimpleNamespace(grouping="provider"),
    )
    return BindingRecord("display.frame-sink@1", "display", record, (), ())


def _request(request_id: str, *, nested: object = None) -> Dict[str, object]:
    message: Dict[str, object] = {
        "type": "display.frame.write",
        "id": request_id,
        "binding_id": "display",
        "frame": {"attachment_id": "frame", "width": 1, "height": 1, "pixel_format": "mono"},
    }
    if nested is not None:
        message["nested"] = nested
    return message


class _Provider:
    def dispatch(
        self,
        message: Dict[str, object],
        attachments: Dict[str, object],
        context: Dict[str, object],
    ) -> Dict[str, object]:
        assert context == {"binding_id": "display"}
        if message["type"] != "display.frame.write":
            return {"ok": False, "error": {"code": "unknown_type"}}
        assert attachments == {"frame": b"x"}
        return {"ok": True, "attachment_id": "frame", "accepted": True}


def _host() -> InProcessDriverHost:
    return InProcessDriverHost((_binding(),), _Provider(), generation=1)


def _build_and_install_fixture(tmp_path: Path) -> Path:
    wheels = tmp_path / "wheels"
    site = tmp_path / "site"
    wheels.mkdir()
    for package in (API_PACKAGE, FIXTURE_PACKAGE):
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(package)],
            check=True,
            capture_output=True,
            text=True,
        )
    for wheel in sorted(wheels.glob("*.whl")):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(site), str(wheel)],
            check=True,
            capture_output=True,
            text=True,
        )
    return site


def _claimed_fixture(site: Path):
    fixture = next(
        distribution for distribution in metadata.distributions(path=[str(site)])
        if distribution.metadata["Name"] == "totem-driver-fixture"
    )
    catalog = CatalogScanner(distributions=lambda: (fixture,)).snapshot()
    binding = Resolver().resolve(
        catalog,
        facts=HardwareFacts.from_mapping({"resource.spi": "spi0.0"}),
        capability_id="display.frame-sink@1",
    ).require_binding()
    return ResourceBroker().claim(binding)


def test_public_conformance_runner_keeps_case_order_and_empty_lifecycle() -> None:
    cases = (
        ConformanceCase("nested", _request("nested", nested={"a": [1, {"b": True}]}), {"frame": b"x"}),
        ConformanceCase("unknown", {"type": "display.unknown", "id": "unknown", "binding_id": "display"}),
    )

    transcript = run_host_conformance(_host, cases)

    assert [item["case"] for item in transcript.items] == ["startup", "nested", "unknown", "close", "close"]
    assert transcript.items[1]["result"] == {
        "type": "display.frame.write.result",
        "id": "nested",
        "ok": True,
        "attachment_id": "frame",
        "accepted": True,
    }
    assert transcript.items[2]["result"] == {
        "type": "display.unknown.result",
        "id": "unknown",
        "ok": False,
        "error": {"code": "unknown_type", "message": "unknown message type"},
    }
    assert run_host_conformance(_host, ()).items == (
        {"case": "startup", "result": {"type": "host.ready", "binding_ids": ["display"]}},
        {"case": "close"},
        {"case": "close"},
    )


def test_dual_host_logical_transcripts_match_and_containment_remains_explicit(tmp_path: Path) -> None:
    site = _build_and_install_fixture(tmp_path)
    claim = _claimed_fixture(site)
    binding_id = claim.binding_id
    cases = (
        ConformanceCase("attachment", {**_request("request-1", nested={"a": [1, {"b": True}]}), "binding_id": binding_id}, {"frame": b"x"}),
        ConformanceCase("unknown", {"type": "display.unknown", "id": "unknown", "binding_id": binding_id}),
    )

    def in_process_factory() -> InProcessDriverHost:
        sys.path.insert(0, str(site))
        try:
            return InProcessDriverHost.start_group((claim,), generation=1)
        finally:
            sys.path.remove(str(site))

    try:
        in_process = run_host_conformance(in_process_factory, cases)
        process = run_host_conformance(lambda: ProcessDriverHost.start(claim, site_packages=site), cases)

        assert process.items == in_process.items
        host = in_process_factory()
        assert host.health()["mode"] == "in_process"
        assert "restart_required" in host.health()
        host.close()
    finally:
        # The fixture's import marker is intentional in an in-process host,
        # but must not escape this isolated conformance test process.
        os.environ.pop("TOTEM_DRIVER_FIXTURE_IMPORTED", None)


def test_sacrificial_fatal_provider_process_cannot_terminate_the_test_daemon() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import os; os._exit(17)"],
        capture_output=True,
        check=False,
    )

    assert result.returncode == 17
    assert os.getpid() != 0
