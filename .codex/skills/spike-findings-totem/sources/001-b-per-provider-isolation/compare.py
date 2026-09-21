#!/usr/bin/env python3
"""Run paired topology trials and write an aggregate comparison."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List


SPIKES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPIKES / "_support"))

from process_topology_bench import run  # noqa: E402


def aggregate(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    memory_metrics = {sample["memory"]["metric"] for sample in samples}
    if len(memory_metrics) != 1:
        raise AssertionError(f"memory metric changed between trials: {memory_metrics!r}")
    return {
        "trials": len(samples),
        "host_process_count": samples[0]["host_process_count"],
        "memory_metric": next(iter(memory_metrics)),
        "median_total_memory_kib": round(
            statistics.median(sample["memory"]["total_kib"] for sample in samples), 3
        ),
        "median_startup_to_all_ready_ms": round(
            statistics.median(sample["startup_to_all_ready_ms"] for sample in samples), 6
        ),
        "median_of_round_trip_medians_ms": round(
            statistics.median(
                sample["round_trip_latency_ms"]["median"] for sample in samples
            ),
            6,
        ),
        "median_of_round_trip_p95_ms": round(
            statistics.median(sample["round_trip_latency_ms"]["p95"] for sample in samples),
            6,
        ),
        "median_replacement_ready_ms": round(
            statistics.median(
                sample["forced_failure"]["replacement_ready_ms"] for sample in samples
            ),
            6,
        ),
        "lost_binding_counts": [
            sample["forced_failure"]["lost_binding_count"] for sample in samples
        ],
        "all_survivor_checks_passed": all(
            sample["forced_failure"]["survivor_checks_passed"]
            == sample["forced_failure"]["unaffected_binding_count"]
            for sample in samples
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("comparison.json")
    )
    args = parser.parse_args()
    if args.trials < 2:
        raise ValueError("at least two trials are required for a comparison")

    samples: Dict[str, List[Dict[str, Any]]] = {
        "per-binding": [],
        "per-provider": [],
    }
    for trial in range(args.trials):
        order = (
            ("per-binding", "per-provider")
            if trial % 2 == 0
            else ("per-provider", "per-binding")
        )
        for topology in order:
            samples[topology].append(run(topology, args.bindings, args.rounds))

    per_binding = aggregate(samples["per-binding"])
    per_provider = aggregate(samples["per-provider"])
    comparison = {
        "schema": "totem.process-topology-comparison@1",
        "binding_count": args.bindings,
        "rounds_per_binding_per_trial": args.rounds,
        "per_binding": per_binding,
        "per_provider": per_provider,
        "ratios_per_binding_over_per_provider": {
            "host_process_count": round(
                per_binding["host_process_count"] / per_provider["host_process_count"], 3
            ),
            "total_memory": round(
                per_binding["median_total_memory_kib"]
                / per_provider["median_total_memory_kib"],
                3,
            ),
            "startup": round(
                per_binding["median_startup_to_all_ready_ms"]
                / per_provider["median_startup_to_all_ready_ms"],
                3,
            ),
        },
        "interpretation": {
            "per_binding": "smallest crash domain; interpreter cost scales with bindings",
            "per_provider": "amortized interpreter; all bindings from that provider fate-share",
            "pi_gate": "repeat with Linux PSS and representative plugin imports on Pi-class hardware",
        },
    }
    args.output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
