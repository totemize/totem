---
phase: HW-01-capability-oriented-hardware-runtime
plan: "30"
subsystem: hardware-compatibility-facades
tags: [python, nfc, storage, capability-client, compatibility-facade, pytest]
requires:
  - phase: HW-01-26
    provides: LegacyHardwareClient translation over the canonical hardware bus.
  - phase: HW-01-28
    provides: Catalog-only legacy registry and explicit lifecycle compatibility contracts.
provides:
  - NFC and storage wrappers that delegate operations only through an injected canonical client.
  - Facade-local lifecycle and close behavior with no provider, lease, filesystem, or transport ownership.
  - Focused local fake-client, storage-value, and import-boundary regression coverage.
affects: [HW-01-31, legacy-device-facades, hardware-api]
tech-stack:
  added: []
  patterns:
    - Historical family wrappers retain configuration only as inert compatibility-boundary data and use LegacyHardwareClient for operations.
    - Storage value imports remain aliases to canonical built-in values while runtime ownership stays outside the facade.
key-files:
  created:
    - tests/unit/test_device_nfc_storage_facades.py
  modified:
    - src/totem/devices/nfc/__init__.py
    - src/totem/devices/nfc/nfc.py
    - src/totem/devices/storage/__init__.py
    - src/totem/devices/storage/device.py
    - src/totem/devices/storage/files.py
key-decisions:
  - "NFC and storage selection inputs remain inert compatibility configuration; wrappers never probe, select, or instantiate a driver."
  - "Initialize and close are facade-local transitions, so shared canonical clients and their leases remain runtime-owned."
patterns-established:
  - "Family facade clean-break tests use recording client fakes plus AST ownership audits, never hardware or provider fixtures."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Legacy NFC and storage names retain constructors, operations, and direct package imports while dispatching only through an injected canonical client.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_device_nfc_storage_facades.py#test_nfc_accepts_an_injected_canonical_client_without_hardware_probe
        status: pass
      - kind: unit
        ref: tests/unit/test_device_nfc_storage_facades.py#test_storage_accepts_an_injected_canonical_client_without_hardware_probe
        status: pass
    human_judgment: false
  - id: D2
    description: NFC and storage facades own no provider, registry, filesystem, transport, or runtime shutdown path.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_device_nfc_storage_facades.py#test_wrapper_sources_have_no_provider_registry_transport_or_filesystem_ownership
        status: pass
      - kind: unit
        ref: tests/unit/test_device_nfc_storage_facades.py#test_close_is_facade_local_and_preserves_shared_client_access
        status: pass
    human_judgment: false
  - id: D3
    description: Storage values and the canonical import boundary remain compatible after NFC/storage facade migration.
    requirement: TST-04
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/test_storage.py tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
metrics:
  duration: "2m"
  completed: "2026-08-26"
status: complete
---

# Phase HW-01 Plan 30: NFC and Storage Wrapper Delegation Summary

**Legacy NFC and storage wrappers now preserve public calls while delegating exclusively to the canonical hardware client, with no local probing, driver loading, file I/O, or lease ownership.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-08-26T17:44:43Z
- **Completed:** 2026-08-26T17:46:51Z
- **Tasks:** 1/1
- **Files modified:** 8

## Accomplishments

- Replaced NFC USB probing and registry-based driver construction with injected `LegacyHardwareClient` read/write delegation.
- Replaced storage `/dev` detection and module loading with canonical storage-message delegation; roots remain inert legacy configuration.
- Added package facade exports and preserved confined storage values as canonical built-in aliases.
- Added local recording-client, close-semantics, AST ownership, storage-value, and import-boundary coverage.

## Task Commits

1. **Task 1: Delegate NFC and storage wrappers without local I/O (RED)** — `2a1d9c1` (`test`)
2. **Task 1: Preserve NFC write return contract** — `925ba1d` (`test`)
3. **Task 1: Delegate NFC and storage wrappers without local I/O (GREEN)** — `68dc60a` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_device_nfc_storage_facades.py tests/unit/test_storage.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 30 passed.
- `.venv/bin/python -m compileall -q src/totem/devices/nfc src/totem/devices/storage` — passed.
- Direct package import check for `NFC`, `Storage`, and `ConfinedStorage` — passed.
- Source audit found no registry, provider, `/dev`, importlib, subprocess, `os`, or file-open ownership in either facade.
- All verification used local injected fakes and temporary storage fixtures only; no SSH, network, deployment, live services, USB/serial/I2C/GPIO, physical device, or hardware-marked tests were contacted.

## Files Created/Modified

- `src/totem/devices/nfc/nfc.py` — Client-only NFC facade with local lifecycle state.
- `src/totem/devices/storage/device.py` — Client-only storage facade with local lifecycle state.
- `src/totem/devices/nfc/__init__.py` and `src/totem/devices/storage/__init__.py` — Public compatibility facade exports.
- `src/totem/devices/storage/files.py` — Readable aliases to canonical built-in storage values.
- `tests/unit/test_device_nfc_storage_facades.py` — Recording-client and AST ownership regression suite.

## Decisions Made

- Keep driver names, mock flags, and storage roots as inert compatibility configuration; canonical runtime selection and resource ownership stay outside wrappers.
- Preserve NFC's historical void `write_data` return while preserving storage's boolean write return.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Contract] Corrected NFC write regression to preserve its void return**
- **Found during:** Task 1 RED refinement.
- **Issue:** The initial regression incorrectly expected `NFC.write_data()` to return `True`, while the existing wrapper contract returned no value.
- **Fix:** Updated the regression to expect `None` before the facade implementation.
- **Files modified:** `tests/unit/test_device_nfc_storage_facades.py`
- **Verification:** Focused facade suite passed with the preserved return contract.
- **Committed in:** `925ba1d`

**2. [Rule 2 - Project Continuity] Recorded the required session journal entry**
- **Found during:** Plan close-out.
- **Issue:** `AGENTS.md` requires completed sessions in the dated journal and index.
- **Fix:** Added this plan's local-only execution result to the journal and index.
- **Files modified:** `.journey/journal/2026-08-26.md`, `.journey/README.md`
- **Verification:** Journal entry and index row identify Plan 01-30 and its focused verification.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2). **Impact:** Both preserve the compatibility and project-continuity contracts; no implementation scope expanded.

## Issues Encountered

None.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- NFC and storage families no longer provide a local hardware ownership backdoor.
- Remaining family-wrapper plans can reuse the injected-client and AST ownership pattern.

## TDD Gate Compliance

- RED `2a1d9c1` failed as expected because `NFC` lacked the injected-client constructor seam.
- GREEN `68dc60a` implemented delegation and passed the focused suite.

## Self-Check: PASSED

- Found all declared NFC/storage facade, storage-value, test, and summary files.
- Found TDD commits `2a1d9c1`, `925ba1d`, and `68dc60a` in repository history.
