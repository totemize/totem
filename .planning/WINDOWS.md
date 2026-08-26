---
schema_version: 1
open_count: 4
waived_count: 0
fixed_count: 15
total_count: 19
last_updated: 2026-08-26T15:49:55.994Z
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
| 10 | HW-01 | unmet-truth | tests/unit/test_driver_contracts.py |  | 17 legacy display contract assertions are intentionally pending Plan 01-28: 13 Waveshare 2.13 checks plus three mock/3.7 DeviceDriver inheritance checks and mock_eink.Driver.health(). | open |  | 2026-08-26T12:48:47.331Z |  |
| 11 | HW-01 | unrun-verify | tests/unit/test_phase1_regression.py |  | SEC-09 final-regression evidence is unavailable until its later owning plan creates this test; Plan 01-15 ran the available resolver/lifecycle evidence subset. | open |  | 2026-08-26T12:53:23.000Z |  |
| 12 | HW-01 | unmet-truth | tests/unit/test_driver_contracts.py |  | Two UPS legacy DeviceDriver/UPSDeviceInterface inheritance assertions (PiSugar2 and Waveshare UPS HAT C) are intentionally pending Plan 01-28; canonical providers preserve telemetry behavior without legacy inheritance. | open |  | 2026-08-26T13:02:21.191Z |  |
| 13 | HW-01 | unmet-truth | tests/unit/test_driver_contracts.py |  | Four NFC legacy contract assertions (ACR122, PN532, and mock_nfc DeviceDriver inheritance plus mock_nfc.health()) are intentionally pending Plan 01-28; canonical provider drivers preserve NFC behavior without legacy inheritance. | open |  | 2026-08-26T13:13:50.155Z |  |
| 14 | HW-01 | deviation | src/totem/hardware/hosts/worker.py |  | Added required storage host dispatch and structural legacy driver validation. | fixed |  | 2026-08-26T14:10:00.433Z | 2026-08-26T14:10:27.848Z |
| 15 | HW-01 | deviation | src/totem/hardware/hosts/in_process.py |  | Corrected shared in-process read/write forwarding after storage integration. | fixed |  | 2026-08-26T14:10:00.488Z | 2026-08-26T14:10:27.903Z |
| 16 | HW-01 | deviation | tests/unit/hardware_runtime/test_radio_resources.py |  | Corrected TDD capability identity assertion to use CapabilityId name and major fields. | fixed |  | 2026-08-26T14:21:20.607Z | 2026-08-26T14:22:11.760Z |
| 17 | HW-01 | deviation | src/totem/hardware/catalog/manifests.py |  | Provider-local manifest lookup was required for Bluetooth discovery beside Wi-Fi. | fixed |  | 2026-08-26T15:10:19.645Z | 2026-08-26T15:11:09.986Z |
| 18 | HW-01 | deviation | src/totem/devices/network/network.py |  | Canonical radio interface bridge was required for deterministic legacy mock-manager coverage. | fixed |  | 2026-08-26T15:10:19.699Z | 2026-08-26T15:11:10.041Z |
| 19 | HW-01 | deviation | src/totem/hardware/api/bus.py |  | Added canonical status and power dispatch so screen readiness can avoid the legacy health route. | fixed |  | 2026-08-26T15:49:42.842Z | 2026-08-26T15:49:55.994Z |

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
    "description": "17 legacy display contract assertions are intentionally pending Plan 01-28: 13 Waveshare 2.13 checks plus three mock/3.7 DeviceDriver inheritance checks and mock_eink.Driver.health().",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T12:48:47.331Z",
    "resolved_at": null
  },
  {
    "id": 11,
    "kind": "unrun-verify",
    "phase": "HW-01",
    "file": "tests/unit/test_phase1_regression.py",
    "line": null,
    "description": "SEC-09 final-regression evidence is unavailable until its later owning plan creates this test; Plan 01-15 ran the available resolver/lifecycle evidence subset.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T12:53:23.000Z",
    "resolved_at": null
  },
  {
    "id": 12,
    "kind": "unmet-truth",
    "phase": "HW-01",
    "file": "tests/unit/test_driver_contracts.py",
    "line": null,
    "description": "Two UPS legacy DeviceDriver/UPSDeviceInterface inheritance assertions (PiSugar2 and Waveshare UPS HAT C) are intentionally pending Plan 01-28; canonical providers preserve telemetry behavior without legacy inheritance.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T13:02:21.191Z",
    "resolved_at": null
  },
  {
    "id": 13,
    "kind": "unmet-truth",
    "phase": "HW-01",
    "file": "tests/unit/test_driver_contracts.py",
    "line": null,
    "description": "Four NFC legacy contract assertions (ACR122, PN532, and mock_nfc DeviceDriver inheritance plus mock_nfc.health()) are intentionally pending Plan 01-28; canonical provider drivers preserve NFC behavior without legacy inheritance.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-26T13:13:50.155Z",
    "resolved_at": null
  },
  {
    "id": 14,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/hosts/worker.py",
    "line": null,
    "description": "Added required storage host dispatch and structural legacy driver validation.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T14:10:00.433Z",
    "resolved_at": "2026-08-26T14:10:27.848Z"
  },
  {
    "id": 15,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/hosts/in_process.py",
    "line": null,
    "description": "Corrected shared in-process read/write forwarding after storage integration.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T14:10:00.488Z",
    "resolved_at": "2026-08-26T14:10:27.903Z"
  },
  {
    "id": 16,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "tests/unit/hardware_runtime/test_radio_resources.py",
    "line": null,
    "description": "Corrected TDD capability identity assertion to use CapabilityId name and major fields.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T14:21:20.607Z",
    "resolved_at": "2026-08-26T14:22:11.760Z"
  },
  {
    "id": 17,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/catalog/manifests.py",
    "line": null,
    "description": "Provider-local manifest lookup was required for Bluetooth discovery beside Wi-Fi.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T15:10:19.645Z",
    "resolved_at": "2026-08-26T15:11:09.986Z"
  },
  {
    "id": 18,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/devices/network/network.py",
    "line": null,
    "description": "Canonical radio interface bridge was required for deterministic legacy mock-manager coverage.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T15:10:19.699Z",
    "resolved_at": "2026-08-26T15:11:10.041Z"
  },
  {
    "id": 19,
    "kind": "deviation",
    "phase": "HW-01",
    "file": "src/totem/hardware/api/bus.py",
    "line": null,
    "description": "Added canonical status and power dispatch so screen readiness can avoid the legacy health route.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-26T15:49:42.842Z",
    "resolved_at": "2026-08-26T15:49:55.994Z"
  }
]
````
