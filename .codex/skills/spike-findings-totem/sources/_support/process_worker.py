#!/usr/bin/env python3
"""Minimal executable child used by the process-topology spikes.

This intentionally imports only the standard library. The experiment measures
the cost and failure domain of the host topology, not a particular driver.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable


def emit(message: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def serve(bindings: Iterable[str]) -> int:
    binding_set = set(bindings)
    emit({"type": "host.ready", "bindings": sorted(binding_set)})

    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            emit({"type": "host.error", "ok": False, "error": str(exc)})
            continue

        request_type = request.get("type")
        request_id = request.get("id")
        binding = request.get("binding")

        if request_type == "host.shutdown":
            emit({"type": "host.shutdown.result", "id": request_id, "ok": True})
            return 0

        if request_type != "capability.ping":
            emit(
                {
                    "type": f"{request_type}.result",
                    "id": request_id,
                    "ok": False,
                    "error": {"code": "unknown_type", "message": "unsupported request"},
                }
            )
            continue

        if binding not in binding_set:
            emit(
                {
                    "type": "capability.ping.result",
                    "id": request_id,
                    "ok": False,
                    "error": {"code": "unknown_binding", "message": str(binding)},
                }
            )
            continue

        emit(
            {
                "type": "capability.ping.result",
                "id": request_id,
                "ok": True,
                "binding": binding,
            }
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", action="append", required=True)
    args = parser.parse_args()
    return serve(args.binding)


if __name__ == "__main__":
    raise SystemExit(main())
