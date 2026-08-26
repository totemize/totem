---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 3
total_count: 3
last_updated: 2026-08-26T11:41:47.839Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | HW-01 | deviation | src/totem/hardware/hosts/process.py |  | Restricted child environment to selected runtime roots instead of forwarding daemon ambient configuration. | fixed |  | 2026-08-26T10:51:32.353Z | 2026-08-26T10:51:51.518Z |
| 2 | HW-01 | deviation | src/totem/hardware/runtime/broker.py |  | Retained the existing lease binding accessor for catalog-to-claim tracer compatibility. | fixed |  | 2026-08-26T11:41:40.670Z | 2026-08-26T11:41:47.785Z |
| 3 | HW-01 | deviation | src/totem/hardware/runtime/broker.py |  | Prevalidated all release owners before deleting any resource entry. | fixed |  | 2026-08-26T11:41:40.723Z | 2026-08-26T11:41:47.839Z |

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
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/runtime/broker.py",
    "line": null,
    "description": "Retained the existing lease binding accessor for catalog-to-claim tracer compatibility.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T11:41:40.670Z",
    "resolved_at": "2026-08-26T11:41:47.785Z"
  },
  {
    "id": 3,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/runtime/broker.py",
    "line": null,
    "description": "Prevalidated all release owners before deleting any resource entry.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T11:41:40.723Z",
    "resolved_at": "2026-08-26T11:41:47.839Z"
  }
]
````
