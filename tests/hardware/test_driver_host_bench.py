"""Opt-in Pi benchmark acceptance contract for the hardware-driver runtime.

Schema tests are controller-safe.  The optional harness is marked ``hardware``
and needs both pytest's ``--run-hardware`` switch and explicit target/allocation
metadata before it can validate a captured device-evidence record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.benchmark_driver_host import (
    ARCHITECTURES,
    PINNED_WORKLOAD,
    BenchmarkEvidenceError,
    architecture_acceptance,
    acceptance_row,
    validate_evidence,
)


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def _complete_evidence(architecture: str = "armv6l") -> dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_scope": "allocated-hardware",
        "hardware_contacted": True,
        "captured_at": "2026-08-26T00:00:00+00:00",
        "attestation": {"operator": "test-operator", "device_identity": "test-device"},
        "target": "allocated-{}".format(architecture),
        "allocation": "ticket-{}".format(architecture),
        "architecture": architecture,
        "platform": {"machine": architecture, "system": "Linux"},
        "python": {"version": "3.9.6"},
        "runtime": {"version": "local-build", "mode": "process", "codec": "canonical-json-v1"},
        "packages": {"totem": "local-build"},
        "grouping": "provider",
        "provider_imports": ["totem.hardware.hosts.process", "totem_driver_api"],
        "startup_to_ready_ms": 25.0,
        "memory": {"steady_kib": 1024, "measurement": "pss", "source": "/proc/123/smaps_rollup"},
        "control_latency_ms": {"p50": 1.0, "p95": 2.0, "samples": 20},
        "frame_transfer": {"bytes": 4000, "p50_ms": 1.5, "p95_ms": 2.5},
        "event_load": {"events": 100, "accepted": 100, "dropped": 0},
        "recovery": {
            "crash": {"recovered": True, "generation_before": 1, "generation_after": 2},
            "hang": {"recovered": True, "generation_before": 2, "generation_after": 3},
        },
        "post_death_leases": {"released": True, "remaining": 0},
        "worker_cleanup": {"workers_remaining": 0, "threads_remaining": 0, "sockets_remaining": 0},
        "rollback": {"procedure": "restore prior package and restart under operator control", "completed": True},
    }


def test_pinned_workload_covers_both_grouping_cases_and_required_faults() -> None:
    assert set(ARCHITECTURES) == {"armv6l", "armv7l", "aarch64"}
    assert {case["grouping"] for case in PINNED_WORKLOAD["cases"]} == {"provider", "binding"}
    assert PINNED_WORKLOAD["frame_transfer"]["bytes"] == 4000
    assert PINNED_WORKLOAD["faults"] == ["crash", "hang"]


def test_complete_evidence_is_accepted_and_has_a_human_row() -> None:
    row = acceptance_row(validate_evidence(_complete_evidence()))

    assert row["run_complete"] is True
    assert row["architecture"] == "armv6l"
    assert row["memory_measurement"] == "pss"


def test_missing_recovery_or_lease_evidence_cannot_be_accepted() -> None:
    evidence = _complete_evidence()
    evidence["post_death_leases"] = {"released": False, "remaining": 1}

    with pytest.raises(BenchmarkEvidenceError, match="post_death_leases"):
        validate_evidence(evidence)


def test_architecture_cannot_be_accepted_without_both_grouping_records() -> None:
    provider = _complete_evidence()
    binding = _complete_evidence()
    binding["grouping"] = "binding"

    pending = architecture_acceptance((provider,), "armv6l")
    complete = architecture_acceptance((provider, binding), "armv6l")

    assert pending["accepted"] is False
    assert pending["missing_groupings"] == ["binding"]
    assert complete["accepted"] is True


def test_non_hardware_or_non_finite_or_duplicate_evidence_cannot_be_accepted() -> None:
    local = _complete_evidence()
    local["hardware_contacted"] = False
    with pytest.raises(BenchmarkEvidenceError, match="hardware_contacted"):
        validate_evidence(local)

    non_finite = _complete_evidence()
    non_finite["startup_to_ready_ms"] = float("nan")
    with pytest.raises(BenchmarkEvidenceError, match="finite"):
        validate_evidence(non_finite)

    provider = _complete_evidence()
    duplicate = _complete_evidence()
    result = architecture_acceptance((provider, duplicate), "armv6l")
    assert result["accepted"] is False
    assert result["duplicate_groupings"] == ["provider"]


@pytest.mark.hardware
def test_allocated_hardware_evidence_is_explicit_and_pre_captured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hardware run validates only explicit local evidence; it never discovers a target."""
    target = "allocated-armv6l"
    allocation = "ticket-armv6l"
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_complete_evidence()), encoding="utf-8")
    monkeypatch.setenv("TOTEM_BENCHMARK_TARGET", target)
    monkeypatch.setenv("TOTEM_BENCHMARK_ALLOCATION", allocation)

    loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert loaded["target"] == target
    assert loaded["allocation"] == allocation
    assert validate_evidence(loaded)["architecture"] == "armv6l"
