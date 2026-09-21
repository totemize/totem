#!/usr/bin/env python3
"""Validate explicit Pi driver-host benchmark evidence without discovering hardware.

This tool deliberately does not open a device, connect to a host, or start a
runtime.  An allocated-device operator runs the pinned workload through the
normal runtime controls, captures the resulting JSON, and uses this program to
validate and render the evidence.  Missing or inconsistent fields fail closed.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
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


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def load_trusted_allocations(path: Path) -> Mapping[str, Mapping[str, str]]:
    """Load controller-owned allocation identities and HMAC verification keys.

    The trust store is intentionally separate from caller-provided evidence and
    must remain controller-local.  It maps allocation id to target, device
    identity, key id, and a base64 HMAC key provisioned to that allocated
    device.  The key never appears in evidence or rendered acceptance output.
    """

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkEvidenceError("cannot load trusted allocation store") from exc
    allocations = _mapping(value, "trusted_allocations").get("allocations")
    if not isinstance(allocations, Mapping) or not allocations:
        raise BenchmarkEvidenceError("trusted allocation store has no allocations")
    normalized: dict[str, Mapping[str, str]] = {}
    for allocation, record in allocations.items():
        allocation_id = _string(allocation, "trusted allocation id")
        item = _mapping(record, "trusted allocation")
        fields = {name: _string(item.get(name), "trusted allocation.{}".format(name)) for name in ("target", "device_identity", "key_id", "hmac_key_b64")}
        try:
            if not base64.b64decode(fields["hmac_key_b64"], validate=True):
                raise ValueError
        except ValueError as exc:
            raise BenchmarkEvidenceError("trusted allocation HMAC key is invalid") from exc
        normalized[allocation_id] = fields
    return normalized


def attest_evidence(value: Mapping[str, object], *, hmac_key: bytes, key_id: str, runtime_build: str) -> Dict[str, object]:
    """Bind a device-captured record to its workload and immutable payload.

    This helper is executed by the allocated-device benchmark runner after its
    measurement capture.  It never opens hardware itself; measurement code is
    deliberately kept in the normal device runtime control path.
    """

    if not hmac_key or not isinstance(key_id, str) or not key_id or not isinstance(runtime_build, str) or not runtime_build:
        raise BenchmarkEvidenceError("attestation inputs are invalid")
    record = dict(value)
    record.pop("attestation", None)
    capture_sha256 = _digest(record)
    body = {
        "target": record.get("target"), "allocation": record.get("allocation"),
        "device_identity": record.get("device_identity"), "workload_sha256": _digest(PINNED_WORKLOAD),
        "runtime_build": runtime_build, "capture_sha256": capture_sha256,
    }
    signature = hmac.new(hmac_key, _canonical_bytes(body), hashlib.sha256).hexdigest()
    return {**record, "attestation": {"algorithm": "hmac-sha256", "key_id": key_id, "workload_sha256": body["workload_sha256"], "runtime_build": runtime_build, "capture_sha256": capture_sha256, "signature": signature}}


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
    if not math.isfinite(result):
        raise BenchmarkEvidenceError("{} must be finite".format(path))
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


def validate_evidence(
    value: object, *, trusted_allocations: Optional[Mapping[str, Mapping[str, str]]] = None,
    allow_synthetic: bool = False,
) -> Dict[str, object]:
    """Return a normalized complete run record or reject it before acceptance.

    A validated record represents a single grouping run.  Architecture-level
    acceptance requires both provider and binding records via
    :func:`architecture_acceptance`.
    """

    evidence = _mapping(value, "evidence")
    _reject_secret_values(evidence)
    if evidence.get("schema_version") != 1:
        raise BenchmarkEvidenceError("schema_version must be 1")
    if evidence.get("evidence_scope") != "allocated-hardware":
        if not (allow_synthetic and evidence.get("evidence_scope") == "local-synthetic-only"):
            raise BenchmarkEvidenceError("evidence_scope must be allocated-hardware")
    if evidence.get("hardware_contacted") is not True and not allow_synthetic:
        raise BenchmarkEvidenceError("hardware_contacted must be true")
    captured_at = _string(evidence.get("captured_at"), "captured_at")
    try:
        parsed_capture = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BenchmarkEvidenceError("captured_at must be an ISO-8601 timestamp") from exc
    if parsed_capture.tzinfo is None or parsed_capture > datetime.now(timezone.utc):
        raise BenchmarkEvidenceError("captured_at must be a past timestamp with timezone")
    target = _string(evidence.get("target"), "target")
    allocation = _string(evidence.get("allocation"), "allocation")
    device_identity = _string(evidence.get("device_identity"), "device_identity")
    if not allow_synthetic:
        _verify_attestation(evidence, trusted_allocations, target, allocation, device_identity)
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
    if _string(runtime.get("mode"), "runtime.mode") != "process":
        raise BenchmarkEvidenceError("runtime.mode must equal the pinned process mode")
    if _string(runtime.get("codec"), "runtime.codec") != "canonical-json-v1":
        raise BenchmarkEvidenceError("runtime.codec must equal the pinned canonical-json-v1 codec")
    packages = _mapping(evidence.get("packages"), "packages")
    if not packages:
        raise BenchmarkEvidenceError("packages must identify the installed distributions")
    grouping = _string(evidence.get("grouping"), "grouping")
    if grouping not in GROUPINGS:
        raise BenchmarkEvidenceError("grouping must be provider or binding")
    provider_imports = evidence.get("provider_imports")
    if provider_imports != PINNED_WORKLOAD["provider_imports"]:
        raise BenchmarkEvidenceError("provider_imports must equal the pinned workload")
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


def _verify_attestation(
    evidence: Mapping[str, object], trusted_allocations: Optional[Mapping[str, Mapping[str, str]]],
    target: str, allocation: str, device_identity: str,
) -> None:
    if trusted_allocations is None:
        raise BenchmarkEvidenceError("trusted allocation verification is required")
    trusted = trusted_allocations.get(allocation)
    if trusted is None or trusted.get("target") != target or trusted.get("device_identity") != device_identity:
        raise BenchmarkEvidenceError("evidence target/allocation is not trusted")
    attestation = _mapping(evidence.get("attestation"), "attestation")
    if attestation.get("algorithm") != "hmac-sha256" or attestation.get("key_id") != trusted.get("key_id"):
        raise BenchmarkEvidenceError("evidence attestation identity is not trusted")
    signature = _string(attestation.get("signature"), "attestation.signature")
    record = dict(evidence)
    record.pop("attestation", None)
    capture_sha256 = _digest(record)
    if attestation.get("capture_sha256") != capture_sha256 or attestation.get("workload_sha256") != _digest(PINNED_WORKLOAD):
        raise BenchmarkEvidenceError("evidence attestation digest does not match capture")
    runtime_build = _string(attestation.get("runtime_build"), "attestation.runtime_build")
    body = {"target": target, "allocation": allocation, "device_identity": device_identity, "workload_sha256": _digest(PINNED_WORKLOAD), "runtime_build": runtime_build, "capture_sha256": capture_sha256}
    try:
        key = base64.b64decode(trusted["hmac_key_b64"], validate=True)
    except (KeyError, ValueError) as exc:
        raise BenchmarkEvidenceError("trusted allocation HMAC key is invalid") from exc
    expected = hmac.new(key, _canonical_bytes(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise BenchmarkEvidenceError("evidence attestation signature is invalid")


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


def architecture_acceptance(
    records: Iterable[Mapping[str, object]], architecture: str, *,
    trusted_allocations: Optional[Mapping[str, Mapping[str, str]]] = None,
) -> Dict[str, object]:
    """Fail closed unless both required process-group measurements are complete."""

    if architecture not in ARCHITECTURES:
        raise BenchmarkEvidenceError("architecture must be one of {}".format(", ".join(ARCHITECTURES)))
    complete = [validate_evidence(record, trusted_allocations=trusted_allocations) for record in records if record.get("architecture") == architecture]
    groupings = {str(record["grouping"]) for record in complete}
    missing = [grouping for grouping in GROUPINGS if grouping not in groupings]
    duplicates = sorted(grouping for grouping in groupings if sum(record["grouping"] == grouping for record in complete) != 1)
    extra = [str(record["grouping"]) for record in complete if str(record["grouping"]) not in GROUPINGS]
    return {
        "architecture": architecture,
        "accepted": not missing and not duplicates and not extra and len(complete) == len(GROUPINGS),
        "missing_groupings": missing,
        "duplicate_groupings": duplicates,
        "extra_groupings": extra,
        "rows": [acceptance_row(record) for record in complete],
    }


def _self_test_evidence() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "evidence_scope": "local-synthetic-only",
        "hardware_contacted": False,
        "captured_at": "2026-08-26T00:00:00+00:00",
        "device_identity": "synthetic",
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


def _load_records(paths: Sequence[str], *, trusted_allocations: Mapping[str, Mapping[str, str]]) -> list[Dict[str, object]]:
    records = []
    for raw_path in paths:
        try:
            value = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BenchmarkEvidenceError("cannot load evidence {}".format(raw_path)) from exc
        records.append(validate_evidence(value, trusted_allocations=trusted_allocations))
    return records


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="validate the local synthetic schema fixture only")
    parser.add_argument("--workload", action="store_true", help="print the pinned workload without executing it")
    parser.add_argument("--run-hardware", action="store_true", help="permit validation of explicit allocated-device evidence")
    parser.add_argument("--target", help="allocated device identifier; never discovered by this tool")
    parser.add_argument("--allocation", help="operator allocation/ticket identifier")
    parser.add_argument("--trusted-allocations", help="controller-local allocation identity/key store")
    parser.add_argument("--evidence-json", action="append", default=[], help="captured evidence record; repeat for both groupings")
    args = parser.parse_args(argv)
    if args.self_test:
        record = validate_evidence(_self_test_evidence(), allow_synthetic=True)
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
        trusted_allocations = load_trusted_allocations(Path(_string(args.trusted_allocations, "--trusted-allocations")))
        records = _load_records(args.evidence_json, trusted_allocations=trusted_allocations)
        for record in records:
            if record["target"] != target or record["allocation"] != allocation:
                raise BenchmarkEvidenceError("target/allocation must match every evidence record")
        matrix = [architecture_acceptance(records, architecture, trusted_allocations=trusted_allocations) for architecture in ARCHITECTURES]
    except BenchmarkEvidenceError as exc:
        parser.error(str(exc))
    print(json.dumps({"workload": PINNED_WORKLOAD, "acceptance_matrix": matrix}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
