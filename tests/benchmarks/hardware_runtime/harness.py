"""Enumerate synthetic local benchmark work without contacting a Totem device."""

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class BenchmarkResult:
    workload: str
    iterations: int
    tasks: int
    evidence_scope: str = "local-synthetic-only"
    pi_acceptance: bool = False
    hardware_contacted: bool = False


def enumerate_local_workload(iterations: int) -> List[Dict[str, object]]:
    if iterations < 1:
        raise ValueError("iterations must be at least one")
    return [
        {"type": "synthetic.ping", "id": "synthetic-{0}".format(index)}
        for index in range(iterations)
    ]


def run_local_synthetic_workload(iterations: int) -> BenchmarkResult:
    tasks = enumerate_local_workload(iterations)
    return BenchmarkResult(workload="synthetic", iterations=iterations, tasks=len(tasks))


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args(argv)
    print(json.dumps(asdict(run_local_synthetic_workload(args.iterations)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
