#!/usr/bin/env python3
import json
from pathlib import Path
import sys


SPIKES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPIKES / "_support"))

from nip5d_framed import MessagePackCodec, run_spike  # noqa: E402


def main() -> int:
    result = run_spike(MessagePackCodec())
    output = Path(__file__).with_name("results.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
