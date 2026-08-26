---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 9
total_count: 10
last_updated: 2026-08-26T12:48:47.331Z
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
| 4 | HW-01 | deviation | src/totem/hardware/runtime/lifecycle.py |  | Corrected idempotent-close re-entry deadlock. | fixed |  | 2026-08-26T11:54:37.356Z | 2026-08-26T11:54:42.274Z |
| 5 | HW-01 | deviation | src/totem/hardware/runtime/lifecycle.py |  | Made aggregate lifecycle snapshots and event snapshots fully immutable. | fixed |  | 2026-08-26T11:54:37.414Z | 2026-08-26T11:54:42.331Z |
| 6 | HW-01 | deviation | src/totem/hardware/hosts/worker.py |  | Reject unknown binding IDs before worker provider dispatch. | fixed |  | 2026-08-26T11:54:37.471Z | 2026-08-26T11:54:42.388Z |
| 7 | HW-01 | deviation | tests/unit/hardware_runtime/test_conformance.py |  | Fixture import marker cleanup retained for package-boundary test isolation | fixed |  | 2026-08-26T12:05:30.497Z | 2026-08-26T12:05:47.435Z |
| 8 | HW-01 | deviation | src/totem/hardware/builtin/display/totem-driver-manifest.json |  | Manifest selector was corrected from a V4-specific predicate to the Waveshare 2.13 family. | fixed |  | 2026-08-26T12:15:34.526Z | 2026-08-26T12:15:48.111Z |
| 9 | HW-01 | deviation | src/totem/hardware/builtin/display/drivers/waveshare_2in13_v3.py | 15 | Restored exact 159-byte V3 full-update LUT after mock initialization detected a shortened transcription. | fixed |  | 2026-08-26T12:24:07.048Z | 2026-08-26T12:24:21.137Z |
| 10 | HW-01 | unmet-truth | tests/unit/test_driver_contracts.py |  | 13 legacy Waveshare contract assertions are intentionally pending Plan 01-28 because they require obsolete DeviceDriver inheritance or removed legacy-base internals. | open |  | 2026-08-26T12:48:47.331Z |  |

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
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/runtime/lifecycle.py",
    "line": null,
    "description": "Corrected idempotent-close re-entry deadlock.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T11:54:37.356Z",
    "resolved_at": "2026-08-26T11:54:42.274Z"
  },
  {
    "id": 5,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/runtime/lifecycle.py",
    "line": null,
    "description": "Made aggregate lifecycle snapshots and event snapshots fully immutable.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T11:54:37.414Z",
    "resolved_at": "2026-08-26T11:54:42.331Z"
  },
  {
    "id": 6,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/hosts/worker.py",
    "line": null,
    "description": "Reject unknown binding IDs before worker provider dispatch.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T11:54:37.471Z",
    "resolved_at": "2026-08-26T11:54:42.388Z"
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "tests/unit/hardware_runtime/test_conformance.py",
    "line": null,
    "description": "Fixture import marker cleanup retained for package-boundary test isolation",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T12:05:30.497Z",
    "resolved_at": "2026-08-26T12:05:47.435Z"
  },
  {
    "id": 8,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/builtin/display/totem-driver-manifest.json",
    "line": null,
    "description": "Manifest selector was corrected from a V4-specific predicate to the Waveshare 2.13 family.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T12:15:34.526Z",
    "resolved_at": "2026-08-26T12:15:48.111Z"
  },
  {
    "id": 9,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/builtin/display/drivers/waveshare_2in13_v3.py",
    "line": 15,
    "description": "Restored exact 159-byte V3 full-update LUT after mock initialization detected a shortened transcription.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T12:24:07.048Z",
    "resolved_at": "2026-08-26T12:24:21.137Z"
  },
  {
    "id": 10,
    "kind": "unmet-truth",
    "phase": "HW-01",
    "file": "tests/unit/test_driver_contracts.py",
    "line": null,
    "description": "13 legacy Waveshare contract assertions are intentionally pending Plan 01-28 because they require obsolete DeviceDriver inheritance or removed legacy-base internals.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T12:48:47.331Z",
    "resolved_at": null
  }
]
````
