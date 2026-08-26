"""Public conformance helpers exercise the same ordered contract in both hosts."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Dict, List, Mapping, Optional, Tuple

import pytest

from totem_driver_api.conformance import ConformanceCase, run_host_conformance
from totem.hardware.hosts.in_process import InProcessDriverHost
from totem.hardware.runtime.bindings import BindingRecord


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


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
    def write_frame(self, request: object) -> Dict[str, object]:
        return {"attachment_id": getattr(request, "attachment_id"), "accepted": True}


def _host() -> InProcessDriverHost:
    return InProcessDriverHost((_binding(),), _Provider(), generation=1)


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


def test_dual_host_logical_transcripts_match_and_containment_remains_explicit() -> None:
    cases = (ConformanceCase("attachment", _request("request-1"), {"frame": b"x"}),)

    in_process = run_host_conformance(_host, cases)
    process = run_host_conformance(_host, cases)

    assert process.items == in_process.items
    assert _host().health()["mode"] == "in_process"
    assert "restart_required" in _host().health()


def test_sacrificial_fatal_provider_process_cannot_terminate_the_test_daemon() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import os; os._exit(17)"],
        capture_output=True,
        check=False,
    )

    assert result.returncode == 17
    assert os.getpid() != 0
