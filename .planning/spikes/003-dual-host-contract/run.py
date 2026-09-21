#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


SPIKES = Path(__file__).resolve().parents[1]
SUPPORT = SPIKES / "_support"
sys.path.insert(0, str(SUPPORT))

from dual_host_fixture import (  # noqa: E402
    CRASH_EXIT_CODE,
    InProcessHost,
    ProcessHost,
    functional_conformance,
)


def hang_probe(mode: str) -> Dict[str, Any]:
    host = InProcessHost(cancellation_grace=0.05) if mode == "in_process" else ProcessHost()
    try:
        deadline = host.request(
            {"type": "fixture.hang", "id": f"hang-{mode}"}, timeout=0.03
        )
        stats_at_deadline = host.stats()
        follow_up = host.request(
            {"type": "fixture.echo", "id": f"after-hang-{mode}", "value": "alive"},
            timeout=0.5,
        )
        if mode == "in_process":
            assert deadline["error"]["code"] == "deadline_exceeded"
            assert stats_at_deadline["contaminated"] is True
            assert stats_at_deadline["live_invocation_threads"] == 1
            assert follow_up["error"]["code"] == "host_contaminated"
            resources_releasable = False
            requires_daemon_restart = True
        else:
            assert deadline["error"]["code"] == "deadline_exceeded"
            assert stats_at_deadline["restarts"] == 1
            assert stats_at_deadline["child_alive"] is True
            assert follow_up["ok"] is True
            resources_releasable = True
            requires_daemon_restart = False
        return {
            "deadline_result": deadline,
            "stats_at_deadline": stats_at_deadline,
            "follow_up": follow_up,
            "resources_releasable": resources_releasable,
            "requires_daemon_restart": requires_daemon_restart,
        }
    finally:
        host.close()


def crash_probes() -> Dict[str, Any]:
    probe = SUPPORT / "host_crash_probe.py"
    in_process = subprocess.run(
        [sys.executable, str(probe), "--mode", "in-process"],
        capture_output=True,
        text=True,
        timeout=10.0,
        check=False,
    )
    assert in_process.returncode == CRASH_EXIT_CODE
    assert not in_process.stdout.strip()

    isolated = subprocess.run(
        [sys.executable, str(probe), "--mode", "process"],
        capture_output=True,
        text=True,
        timeout=10.0,
        check=False,
    )
    if isolated.returncode != 0:
        raise AssertionError(
            f"process crash probe failed: rc={isolated.returncode} stderr={isolated.stderr!r}"
        )
    payload = json.loads(isolated.stdout)
    assert payload["crash_result"]["error"]["code"] == "host_crashed"
    assert payload["follow_up"]["ok"] is True
    assert payload["stats"]["last_exit_code"] == CRASH_EXIT_CODE
    assert payload["stats"]["restarts"] == 1
    return {
        "in_process": {
            "probe_exit_code": in_process.returncode,
            "daemon_survived": False,
        },
        "process": {
            "probe_exit_code": isolated.returncode,
            "daemon_survived": True,
            "driver_exit_code": payload["stats"]["last_exit_code"],
            "restarted": payload["stats"]["restarts"] == 1,
            "follow_up_succeeded": payload["follow_up"]["ok"],
        },
    }


def main() -> int:
    in_process_host = InProcessHost()
    process_host = ProcessHost()
    try:
        in_process = functional_conformance(in_process_host)
        isolated = functional_conformance(process_host)
    finally:
        in_process_host.close()
        process_host.close()

    assert in_process["checks"] == isolated["checks"]
    assert in_process["transcript"] == isolated["transcript"]

    result = {
        "schema": "totem.dual-driver-host-spike@1",
        "functional_conformance": {
            "passed_per_host": len(in_process["checks"]),
            "checks": in_process["checks"],
            "transcripts_identical": True,
            "in_process_stats": in_process["stats"],
            "process_stats": isolated["stats"],
        },
        "uncooperative_hang": {
            "in_process": hang_probe("in_process"),
            "process": hang_probe("process"),
        },
        "native_style_crash": crash_probes(),
        "contract_refinement": {
            "same": [
                "logical request/result/event envelopes",
                "attachment validation",
                "structured provider errors",
                "caller-visible deadline result",
            ],
            "different": [
                "hard termination and restart",
                "native crash containment",
                "safe resource-lease release after uncooperative timeout",
            ],
        },
    }
    output = Path(__file__).with_name("results.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
