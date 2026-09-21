#!/usr/bin/env python3
"""Compare per-binding and per-provider executable child topologies."""

from __future__ import annotations

import argparse
import json
import os
import platform
import select
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


HERE = Path(__file__).resolve().parent
WORKER = HERE / "process_worker.py"


class Host:
    def __init__(self, bindings: Sequence[str]) -> None:
        self.bindings = tuple(bindings)
        command = [sys.executable, str(WORKER)]
        for binding in self.bindings:
            command.extend(("--binding", binding))
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def receive(self, timeout: float = 5.0) -> Dict[str, Any]:
        if self.process.stdout is None:
            raise RuntimeError("worker stdout is unavailable")
        readable, _, _ = select.select([self.process.stdout], [], [], timeout)
        if not readable:
            detail = ""
            if self.process.poll() is not None and self.process.stderr is not None:
                detail = self.process.stderr.read().strip()
            raise TimeoutError(
                f"worker {self.process.pid} produced no response; "
                f"exit={self.process.poll()} stderr={detail!r}"
            )
        line = self.process.stdout.readline()
        if not line:
            raise EOFError(f"worker {self.process.pid} closed stdout")
        return json.loads(line)

    def send(self, message: Dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("worker stdin is unavailable")
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def ping(self, binding: str, request_id: str) -> float:
        started = time.perf_counter_ns()
        self.send({"type": "capability.ping", "id": request_id, "binding": binding})
        response = self.receive()
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        expected = {
            "type": "capability.ping.result",
            "id": request_id,
            "ok": True,
            "binding": binding,
        }
        if response != expected:
            raise AssertionError(f"unexpected ping response: {response!r}")
        return elapsed_ms

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.send({"type": "host.shutdown", "id": "shutdown"})
            response = self.receive(timeout=2.0)
            if response.get("type") != "host.shutdown.result":
                raise AssertionError(f"unexpected shutdown response: {response!r}")
            self.process.wait(timeout=2.0)
        except (BrokenPipeError, EOFError, TimeoutError, subprocess.TimeoutExpired):
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2.0)


def percentile(values: Sequence[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def linux_memory_kib(pid: int) -> Tuple[str, int]:
    values: Dict[str, int] = {}
    with open(f"/proc/{pid}/smaps_rollup", "r", encoding="utf-8") as handle:
        for line in handle:
            key, _, remainder = line.partition(":")
            if key in {"Pss", "Rss"}:
                values[key] = int(remainder.strip().split()[0])
    if "Pss" in values:
        return "pss_kib", values["Pss"]
    return "rss_kib", values["Rss"]


def portable_memory_kib(pid: int) -> Tuple[str, int]:
    if sys.platform.startswith("linux") and Path(f"/proc/{pid}/smaps_rollup").exists():
        return linux_memory_kib(pid)
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=True,
        capture_output=True,
        text=True,
    )
    return "rss_kib", int(result.stdout.strip())


def groups_for(topology: str, binding_ids: Sequence[str]) -> List[Tuple[str, ...]]:
    if topology == "per-binding":
        return [(binding,) for binding in binding_ids]
    if topology == "per-provider":
        return [tuple(binding_ids)]
    raise ValueError(f"unsupported topology: {topology}")


def start_hosts(groups: Iterable[Sequence[str]]) -> Tuple[List[Host], float]:
    started = time.perf_counter_ns()
    hosts = [Host(group) for group in groups]
    for host in hosts:
        ready = host.receive()
        if ready != {"type": "host.ready", "bindings": sorted(host.bindings)}:
            raise AssertionError(f"unexpected ready message: {ready!r}")
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return hosts, elapsed_ms


def binding_hosts(hosts: Sequence[Host]) -> Dict[str, Host]:
    return {binding: host for host in hosts for binding in host.bindings}


def run(topology: str, binding_count: int, rounds: int) -> Dict[str, Any]:
    if binding_count < 2:
        raise ValueError("binding_count must be at least 2 to measure a failure domain")
    if rounds < 1:
        raise ValueError("rounds must be positive")

    binding_ids = [f"binding-{index:02d}" for index in range(binding_count)]
    groups = groups_for(topology, binding_ids)
    hosts: List[Host] = []
    try:
        hosts, startup_ms = start_hosts(groups)
        memory_samples = [portable_memory_kib(host.process.pid) for host in hosts]
        memory_metrics = {name for name, _ in memory_samples}
        if len(memory_metrics) != 1:
            raise AssertionError(f"mixed memory metrics: {memory_metrics!r}")
        memory_metric = memory_samples[0][0]
        memory_by_host = [value for _, value in memory_samples]

        mapping = binding_hosts(hosts)
        latencies: List[float] = []
        for round_number in range(rounds):
            for binding in binding_ids:
                request_id = f"ping-{round_number:04d}-{binding}"
                latencies.append(mapping[binding].ping(binding, request_id))

        victim_index = 0
        victim = hosts[victim_index]
        lost_bindings = list(victim.bindings)
        victim.process.terminate()
        victim.process.wait(timeout=3.0)

        unaffected = [binding for binding in binding_ids if binding not in lost_bindings]
        survivor_checks = 0
        for binding in unaffected:
            response_time = mapping[binding].ping(binding, f"survivor-{binding}")
            if response_time < 0:
                raise AssertionError("monotonic clock returned a negative duration")
            survivor_checks += 1

        recovery_started = time.perf_counter_ns()
        replacement, _ = start_hosts([victim.bindings])
        recovery_ms = (time.perf_counter_ns() - recovery_started) / 1_000_000
        hosts[victim_index] = replacement[0]
        mapping = binding_hosts(hosts)
        for binding in lost_bindings:
            mapping[binding].ping(binding, f"recovered-{binding}")

        return {
            "schema": "totem.process-topology-benchmark@1",
            "topology": topology,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "binding_count": binding_count,
            "host_process_count": len(groups),
            "requests": len(latencies),
            "startup_to_all_ready_ms": round(startup_ms, 3),
            "memory": {
                "metric": memory_metric,
                "total_kib": sum(memory_by_host),
                "per_host_kib": memory_by_host,
                "note": (
                    "PSS apportions shared pages across processes."
                    if memory_metric == "pss_kib"
                    else "RSS is a portable fallback and may double-count shared pages."
                ),
            },
            "round_trip_latency_ms": {
                "median": round(statistics.median(latencies), 6),
                "p95": round(percentile(latencies, 0.95), 6),
                "maximum": round(max(latencies), 6),
            },
            "forced_failure": {
                "terminated_host_bindings": lost_bindings,
                "lost_binding_count": len(lost_bindings),
                "unaffected_binding_count": len(unaffected),
                "survivor_checks_passed": survivor_checks,
                "replacement_ready_ms": round(recovery_ms, 3),
                "recovered_bindings_verified": len(lost_bindings),
            },
            "scope": "empty CPython executable host using line-delimited JSON over pipes",
        }
    finally:
        for host in hosts:
            host.stop()


def main(topology: str, default_output: Path) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    result = run(topology, args.bindings, args.rounds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0
