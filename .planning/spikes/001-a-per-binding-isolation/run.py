#!/usr/bin/env python3
from pathlib import Path
import sys


SPIKES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPIKES / "_support"))

from process_topology_bench import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main("per-binding", Path(__file__).with_name("results.json")))
