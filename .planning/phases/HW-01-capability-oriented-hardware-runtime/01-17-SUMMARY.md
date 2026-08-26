---
phase: HW-01-capability-oriented-hardware-runtime
plan: "17"
subsystem: hardware-nfc-provider
tags: [nfc, acr122, pn532, mock-transport, capability, process-host, compatibility-facade, pytest]
requires:
  - phase: HW-01-10
    provides: Matching process and in-process driver-host conformance boundary.
  - phase: HW-01-16
    provides: Import-free, lease-gated built-in provider and compatibility-facade pattern.
provides:
  - Versioned nfc.tag@1 public read, write, and presence-poll contracts with bounded JSON-safe payloads.
  - Import-free built-in NFC manifest with explicit ACR122 USB, PN532 USB/serial/I2C, and test-only mock evidence validation.
  - Canonical ACR122, PN532, and mock NFC drivers plus exact historical driver re-export facades.
affects: [HW-01-28, legacy-contracts, nfc-facade, hardware-runtime]
tech-stack:
  added: []
  patterns:
    - NFC capability payloads are validated and base64-encoded before dispatch to a selected, claimed transport.
    - Process and in-process hosts share the same nfc.tag.read/write/poll envelopes and structured failures.
key-files:
  created:
    - packages/totem-driver-api/src/totem_driver_api/capabilities/nfc.py
    - src/totem/hardware/builtin/nfc/provider.py
    - src/totem/hardware/builtin/nfc/totem-driver-manifest.json
    - tests/unit/hardware_runtime/test_builtin_nfc.py
  modified:
    - pyproject.toml
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/hosts/in_process.py
    - src/totem/devices/nfc/drivers/acr122.py
    - src/totem/devices/nfc/drivers/pn532.py
    - src/totem/devices/nfc/drivers/mock_nfc.py
key-decisions:
  - "Use nfc.tag@1 with bounded base64 JSON values so untrusted NFC write data is rejected before provider I/O."
  - "Keep mock NFC as an explicit, evidence-free test selection; unsupported hardware never selects mock behavior."
  - "Retain the four obsolete NFC legacy-contract assertions as a Plan 01-28 migration window rather than reintroducing legacy inheritance or ownership."
patterns-established:
  - "A capability that adds public operations must extend worker dispatch and the in-process cancellation proxy together, then prove transcript parity."
requirements-completed: [HWR-02, SPI-06, TST-04]
coverage:
  - id: D1
    description: ACR122, PN532, and explicit mock NFC behavior is exposed by a bounded nfc.tag@1 provider through both host modes.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_nfc.py#test_nfc_provider_has_matching_dual_host_read_write_poll_conformance
        status: pass
    human_judgment: false
  - id: D2
    description: NFC catalog resolution remains import-free and provider dispatch validates claims, exact evidence, and bounded writes before transport access.
    requirement: SPI-06
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_nfc.py#test_provider_requires_exact_evidence_unambiguous_selection_and_leases_before_io
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_nfc.py#test_catalog_reads_nfc_manifest_without_importing_provider_or_transports
        status: pass
    human_judgment: false
  - id: D3
    description: Historical NFC driver modules resolve to canonical provider classes and contain no registry or runtime ownership.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_nfc.py#test_legacy_nfc_sources_have_no_registry_or_runtime_ownership
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_nfc.py tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
duration: 4min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 17: Built-in NFC Provider Summary

**ACR122, PN532, and explicit mock NFC now run through a bounded, lease-gated `nfc.tag@1` provider with process/in-process parity and exact legacy import facades.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-26T13:10:09Z
- **Completed:** 2026-08-26T13:13:54Z
- **Tasks:** 1/1
- **Files modified:** 16

## Accomplishments

- Added strict NFC public contracts: reads encode bytes as bounded JSON-safe base64, writes reject malformed or oversized caller values, and polling returns an explicit boolean result.
- Registered `builtin.nfc` through an import-free manifest; ACR122 requires its exact USB VID/PID, PN532 accepts exactly one supported USB/serial/I2C evidence mode, and mock is explicit-only.
- Moved all concrete NFC implementations under `totem.hardware.builtin.nfc`, preserved the mock card's initial/read/write state behavior, and reduced every old driver path to a canonical re-export.
- Added both-host conformance, resolver, manifest-before-import, resource-lease, bounded-payload, identity, and AST source-boundary coverage using mocks only.

## Task Commits

1. **Task 1: Catalog PN532, ACR122, and mock NFC providers by stable evidence (RED)** — `d4cd770` (`test`)
2. **Task 1: Catalog PN532, ACR122, and mock NFC providers by stable evidence (GREEN)** — `4190c59` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_nfc.py tests/unit/hardware_runtime/test_builtin_power.py tests/unit/hardware_runtime/test_conformance.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 26 passed.
- Manifest-before-import audit — passed; catalog scanning imported neither the NFC provider nor concrete NFC drivers.
- Legacy facade AST/source audit — passed; all three NFC driver modules contain one canonical import, `__all__`, and no provider, registry, or runtime ownership.
- `.venv/bin/python -m pytest tests/unit/test_driver_contracts.py -k 'nfc' -q` — expected 4 stale assertions, tracked in WINDOWS entry 13 for Plan 01-28.

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/capabilities/nfc.py` — Versioned bounded NFC values and request/result validation.
- `src/totem/hardware/builtin/nfc/` — Import-free manifest, selection/lease provider, and canonical ACR122/PN532/mock implementations.
- `src/totem/hardware/hosts/worker.py` and `src/totem/hardware/hosts/in_process.py` — Shared `nfc.tag.read`, `nfc.tag.write`, and `nfc.tag.poll` host dispatch.
- `src/totem/devices/nfc/drivers/` — Exact canonical compatibility re-exports.
- `tests/unit/hardware_runtime/test_builtin_nfc.py` — Mock-only catalog, safety, dual-host, compatibility, and source-audit regression tests.

## Decisions Made

- NFC write values are constrained to 4096 bytes and use strict base64 at the logical protocol boundary, preventing malformed or excessive writes from reaching a selected transport.
- Driver selection requires one non-mock evidence mode and a leased NFC reader claim before initialization; mock selection requires explicit test configuration.
- Kept legacy `DeviceDriver` inheritance and mock-health expectations out of canonical NFC code. The exact four resulting stale assertions are a dependency-ordered Plan 01-28 window.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Extended both host dispatchers for the public NFC operations**
- **Found during:** Task 1 (Catalog PN532, ACR122, and mock NFC providers by stable evidence)
- **Issue:** Existing worker and in-process host code only dispatched display and power operations, so a new public NFC provider could not satisfy the required dual-host contract.
- **Fix:** Added matching `nfc.tag.read`, `nfc.tag.write`, and `nfc.tag.poll` dispatch/proxy methods with structured invalid-request handling.
- **Files modified:** `src/totem/hardware/hosts/worker.py`, `src/totem/hardware/hosts/in_process.py`
- **Verification:** Both-host conformance transcript is identical in `test_builtin_nfc.py`.
- **Committed in:** `4190c59` (part of Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Required for the planned public capability to operate equivalently in both host modes; no scope expansion beyond the shared host contract.

## Known Stubs

None.

## Issues Encountered

- The local virtual environment does not include the optional `black` module, so no formatter command was run; focused pytest, compile, manifest, and source-boundary verification passed without hardware access.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- NFC now follows the canonical provider and compatibility-facade pattern required by Plan 01-28.
- WINDOWS entry 13 records the four exact stale NFC legacy-contract assertions; Plan 01-28 owns their cleanup.

## Self-Check: PASSED

- Found all canonical capability, manifest, provider, driver, facade, and test files listed above.
- Found task commits `d4cd770` and `4190c59` in git history.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
