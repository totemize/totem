#!/usr/bin/env python3
"""Validate explicit Pi driver-host benchmark evidence without discovering hardware.

This tool deliberately does not open a device, connect to a host, or start a
runtime.  An allocated-device operator runs the pinned workload through the
normal runtime controls, captures the resulting JSON, and uses this program to
validate and render the evidence.  Missing or inconsistent fields fail closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence


ARCHITECTURES = ("armv6l", "armv7l", "aarch64")
GROUPINGS = ("provider", "binding")
PINNED_WORKLOAD: Dict[str, object] = {
    "schema_version": 1,
    "provider_imports": ["totem.hardware.hosts.process", "totem_driver_api"],
    "cases": [
        {"grouping": "provider", "mode": "process"},
        {"grouping": "binding", "mode": "process"},
    ],
    "control_requests": 20,
    "frame_transfer": {"bytes": 4000, "attachment": "display-frame", "media_type": "application/octet-stream"},
    "event_load": {"events": 100, "maximum_dropped": 0},
    "faults": ["crash", "hang"],
    "required_cleanup": ["workers_remaining", "threads_remaining", "sockets_remaining"],
}


class BenchmarkEvidenceError(ValueError):
    """Raised when a record cannot be used as Pi acceptance evidence."""


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BenchmarkEvidenceError("{} must be an object".format(path))
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkEvidenceError("{} must be a non-empty string".format(path))
    return value


def _number(value: object, path: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkEvidenceError("{} must be numeric".format(path))
    result = float(value)
    if positive and result <= 0:
        raise BenchmarkEvidenceError("{} must be greater than zero".format(path))
    if not positive and result < 0:
        raise BenchmarkEvidenceError("{} must not be negative".format(path))
    return result


def _integer(value: object, path: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BenchmarkEvidenceError("{} must be an integer".format(path))
    if positive and value <= 0:
        raise BenchmarkEvidenceError("{} must be greater than zero".format(path))
    if not positive and value < 0:
        raise BenchmarkEvidenceError("{} must not be negative".format(path))
    return value


def _reject_secret_values(value: object, path: str = "evidence") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(word in key_text for word in ("credential", "secret", "token", "password")):
                raise BenchmarkEvidenceError("{} contains a secret-bearing field".format(path))
            _reject_secret_values(nested, "{}.{}".format(path, key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secret_values(nested, "{}[{}]".format(path, index))


def validate_evidence(value: object) -> Dict[str, object]:
    """Return a normalized complete run record or reject it before acceptance.

    A validated record represents a single grouping run.  Architecture-level
    acceptance requires both provider and binding records via
    :func:`architecture_acceptance`.
    """

    evidence = _mapping(value, "evidence")
    _reject_secret_values(evidence)
    if evidence.get("schema_version") != 1:
        raise BenchmarkEvidenceError("schema_version must be 1")
    target = _string(evidence.get("target"), "target")
    allocation = _string(evidence.get("allocation"), "allocation")
    architecture = _string(evidence.get("architecture"), "architecture")
    if architecture not in ARCHITECTURES:
        raise BenchmarkEvidenceError("architecture must be one of {}".format(", ".join(ARCHITECTURES)))
    platform = _mapping(evidence.get("platform"), "platform")
    if _string(platform.get("machine"), "platform.machine") != architecture:
        raise BenchmarkEvidenceError("platform.machine must match architecture")
    _string(platform.get("system"), "platform.system")
    python = _mapping(evidence.get("python"), "python")
    _string(python.get("version"), "python.version")
    runtime = _mapping(evidence.get("runtime"), "runtime")
    _string(runtime.get("version"), "runtime.version")
    if _string(runtime.get("mode"), "runtime.mode") not in {"process", "in_process"}:
        raise BenchmarkEvidenceError("runtime.mode must name a supported host mode")
    _string(runtime.get("codec"), "runtime.codec")
    packages = _mapping(evidence.get("packages"), "packages")
    if not packages:
        raise BenchmarkEvidenceError("packages must identify the installed distributions")
    grouping = _string(evidence.get("grouping"), "grouping")
    if grouping not in GROUPINGS:
        raise BenchmarkEvidenceError("grouping must be provider or binding")
    provider_imports = evidence.get("provider_imports")
    if not isinstance(provider_imports, list) or not provider_imports or not all(isinstance(item, str) and item for item in provider_imports):
        raise BenchmarkEvidenceError("provider_imports must list realistic provider imports")
    _number(evidence.get("startup_to_ready_ms"), "startup_to_ready_ms")
    memory = _mapping(evidence.get("memory"), "memory")
    _number(memory.get("steady_kib"), "memory.steady_kib")
    if _string(memory.get("measurement"), "memory.measurement") not in {"pss", "rss_fallback"}:
        raise BenchmarkEvidenceError("memory.measurement must be pss or rss_fallback")
    source = _string(memory.get("source"), "memory.source")
    if memory["measurement"] == "pss" and not source.endswith("/smaps_rollup"):
        raise BenchmarkEvidenceError("memory.source must identify smaps_rollup when reporting PSS")
    latency = _mapping(evidence.get("control_latency_ms"), "control_latency_ms")
    p50 = _number(latency.get("p50"), "control_latency_ms.p50")
    if _number(latency.get("p95"), "control_latency_ms.p95") < p50:
        raise BenchmarkEvidenceError("control_latency_ms.p95 must be at least p50")
    _integer(latency.get("samples"), "control_latency_ms.samples", positive=True)
    frame = _mapping(evidence.get("frame_transfer"), "frame_transfer")
    if _integer(frame.get("bytes"), "frame_transfer.bytes", positive=True) != 4000:
        raise BenchmarkEvidenceError("frame_transfer.bytes must equal the pinned 4000-byte frame")
    _number(frame.get("p50_ms"), "frame_transfer.p50_ms")
    _number(frame.get("p95_ms"), "frame_transfer.p95_ms")
    events = _mapping(evidence.get("event_load"), "event_load")
    if _integer(events.get("events"), "event_load.events", positive=True) != PINNED_WORKLOAD["event_load"]["events"]:
        raise BenchmarkEvidenceError("event_load.events must equal the pinned workload")
    if _integer(events.get("accepted"), "event_load.accepted") + _integer(events.get("dropped"), "event_load.dropped") != events["events"]:
        raise BenchmarkEvidenceError("event_load accepted and dropped counts must cover all events")
    recovery = _mapping(evidence.get("recovery"), "recovery")
    for fault in PINNED_WORKLOAD["faults"]:
        result = _mapping(recovery.get(fault), "recovery.{}".format(fault))
        if result.get("recovered") is not True:
            raise BenchmarkEvidenceError("recovery.{}.recovered must be true".format(fault))
        before = _integer(result.get("generation_before"), "recovery.{}.generation_before".format(fault), positive=True)
        after = _integer(result.get("generation_after"), "recovery.{}.generation_after".format(fault), positive=True)
        if after <= before:
            raise BenchmarkEvidenceError("recovery.{} must advance generation".format(fault))
    leases = _mapping(evidence.get("post_death_leases"), "post_death_leases")
    if leases.get("released") is not True or _integer(leases.get("remaining"), "post_death_leases.remaining") != 0:
        raise BenchmarkEvidenceError("post_death_leases must confirm release with no remaining leases")
    cleanup = _mapping(evidence.get("worker_cleanup"), "worker_cleanup")
    for field in PINNED_WORKLOAD["required_cleanup"]:
        if _integer(cleanup.get(field), "worker_cleanup.{}".format(field)) != 0:
            raise BenchmarkEvidenceError("worker_cleanup.{} must be zero".format(field))
    rollback = _mapping(evidence.get("rollback"), "rollback")
    _string(rollback.get("procedure"), "rollback.procedure")
    if rollback.get("completed") is not True:
        raise BenchmarkEvidenceError("rollback.completed must be true")
    return dict(evidence)


def acceptance_row(evidence: Mapping[str, object]) -> Dict[str, object]:
    """Project one validated run into a credential-free human-table row."""

    memory = _mapping(evidence["memory"], "memory")
    return {
        "architecture": evidence["architecture"],
        "grouping": evidence["grouping"],
        "measurement_complete": True,
        "memory_measurement": memory["measurement"],
        "startup_to_ready_ms": evidence["startup_to_ready_ms"],
        "control_p95_ms": _mapping(evidence["control_latency_ms"], "control_latency_ms")["p95"],
        "frame_p95_ms": _mapping(evidence["frame_transfer"], "frame_transfer")["p95_ms"],
        "run_complete": True,
    }


def architecture_acceptance(records: Iterable[Mapping[str, object]], architecture: str) -> Dict[str, object]:
    """Fail closed unless both required process-group measurements are complete."""

    if architecture not in ARCHITECTURES:
        raise BenchmarkEvidenceError("architecture must be one of {}".format(", ".join(ARCHITECTURES)))
    complete = [validate_evidence(record) for record in records if record.get("architecture") == architecture]
    groupings = {str(record["grouping"]) for record in complete}
    missing = [grouping for grouping in GROUPINGS if grouping not in groupings]
    return {
        "architecture": architecture,
        "accepted": not missing,
        "missing_groupings": missing,
        "rows": [acceptance_row(record) for record in complete],
    }


def _self_test_evidence() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "target": "local-self-test",
        "allocation": "not-a-hardware-allocation",
        "architecture": "armv6l",
        "platform": {"machine": "armv6l", "system": "Linux"},
        "python": {"version": "3.9"},
        "runtime": {"version": "self-test", "mode": "process", "codec": "canonical-json-v1"},
        "packages": {"totem": "self-test"},
        "grouping": "provider",
        "provider_imports": list(PINNED_WORKLOAD["provider_imports"]),
        "startup_to_ready_ms": 1.0,
        "memory": {"steady_kib": 1, "measurement": "rss_fallback", "source": "synthetic"},
        "control_latency_ms": {"p50": 1.0, "p95": 1.0, "samples": 20},
        "frame_transfer": {"bytes": 4000, "p50_ms": 1.0, "p95_ms": 1.0},
        "event_load": {"events": 100, "accepted": 100, "dropped": 0},
        "recovery": {"crash": {"recovered": True, "generation_before": 1, "generation_after": 2}, "hang": {"recovered": True, "generation_before": 2, "generation_after": 3}},
        "post_death_leases": {"released": True, "remaining": 0},
        "worker_cleanup": {"workers_remaining": 0, "threads_remaining": 0, "sockets_remaining": 0},
        "rollback": {"procedure": "self-test only", "completed": True},
    }


def _load_records(paths: Sequence[str]) -> list[Dict[str, object]]:
    records = []
    for raw_path in paths:
        try:
            value = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BenchmarkEvidenceError("cannot load evidence {}".format(raw_path)) from exc
        records.append(validate_evidence(value))
    return records


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="validate the local synthetic schema fixture only")
    parser.add_argument("--workload", action="store_true", help="print the pinned workload without executing it")
    parser.add_argument("--run-hardware", action="store_true", help="permit validation of explicit allocated-device evidence")
    parser.add_argument("--target", help="allocated device identifier; never discovered by this tool")
    parser.add_argument("--allocation", help="operator allocation/ticket identifier")
    parser.add_argument("--evidence-json", action="append", default=[], help="captured evidence record; repeat for both groupings")
    args = parser.parse_args(argv)
    if args.self_test:
        record = validate_evidence(_self_test_evidence())
        print(json.dumps({"evidence_scope": "local-synthetic-only", "hardware_contacted": False, "pi_acceptance": False, "row": acceptance_row(record)}, sort_keys=True))
        return 0
    if args.workload:
        print(json.dumps(PINNED_WORKLOAD, sort_keys=True))
        return 0
    if not args.run_hardware:
        parser.error("hardware validation requires --run-hardware, --target, --allocation, and --evidence-json")
    target = _string(args.target, "--target")
    allocation = _string(args.allocation, "--allocation")
    if not args.evidence_json:
        parser.error("hardware validation requires at least one --evidence-json")
    try:
        records = _load_records(args.evidence_json)
        for record in records:
            if record["target"] != target or record["allocation"] != allocation:
                raise BenchmarkEvidenceError("target/allocation must match every evidence record")
        matrix = [architecture_acceptance(records, architecture) for architecture in ARCHITECTURES]
    except BenchmarkEvidenceError as exc:
        parser.error(str(exc))
    print(json.dumps({"workload": PINNED_WORKLOAD, "acceptance_matrix": matrix}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
