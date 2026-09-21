#!/usr/bin/env python3
"""Sacrificial process used to test a provider-level os._exit crash."""

import argparse
import json

from dual_host_fixture import InProcessHost, ProcessHost


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("in-process", "process"), required=True)
    args = parser.parse_args()

    host = InProcessHost() if args.mode == "in-process" else ProcessHost()
    try:
        crash_result = host.request({"type": "fixture.crash", "id": "crash-1"}, timeout=1.0)
        follow_up = host.request(
            {"type": "fixture.echo", "id": "after-crash", "value": "alive"},
            timeout=1.0,
        )
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "crash_result": crash_result,
                    "follow_up": follow_up,
                    "stats": host.stats(),
                },
                separators=(",", ":"),
            )
        )
        return 0
    finally:
        host.close()


if __name__ == "__main__":
    raise SystemExit(main())
