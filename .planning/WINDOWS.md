---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 1
total_count: 1
last_updated: 2026-08-26T10:51:51.518Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | HW-01 | deviation | src/totem/hardware/hosts/process.py |  | Restricted child environment to selected runtime roots instead of forwarding daemon ambient configuration. | fixed |  | 2026-08-26T10:51:32.353Z | 2026-08-26T10:51:51.518Z |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/hosts/process.py",
    "line": null,
    "description": "Restricted child environment to selected runtime roots instead of forwarding daemon ambient configuration.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T10:51:32.353Z",
    "resolved_at": "2026-08-26T10:51:51.518Z"
  }
]
````
