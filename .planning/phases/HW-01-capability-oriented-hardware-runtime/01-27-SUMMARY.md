---
phase: HW-01-capability-oriented-hardware-runtime
plan: "27"
subsystem: hardware-compatibility
tags: [python, compatibility, managers, capability-client, radio, pytest]
requires:
  - phase: HW-01-26
    provides: LegacyHardwareClient and canonical bus-backed compatibility routes.
provides:
  - Five compatibility-only manager facades with no driver, catalog, provider, resource, or lifecycle ownership.
  - Explicit Wi-Fi and Bluetooth action translation for every public NetworkManager operation.
  - Exhaustive injected-client coverage for manager constructors, methods, close behavior, and import boundaries.
affects: [HW-01-28, legacy-clean-break, hardware-api]
tech-stack:
  added: []
  patterns:
    - Legacy manager names retain caller-facing operations while delegating only through LegacyHardwareClient.
    - A manager close is facade-local and never closes an injected client, runtime, provider, or lease.
key-files:
  created:
    - tests/unit/test_manager_facades.py
  modified:
    - src/totem/compat/hardware_client.py
    - src/totem/managers/display_manager.py
    - src/totem/managers/ups_manager.py
    - src/totem/managers/nfc_manager.py
    - src/totem/managers/storage_manager.py
    - src/totem/managers/network_manager.py
    - tests/unit/test_mock_transports.py
    - tests/unit/test_radio_primitives.py
    - tests/unit/test_storage.py
key-decisions:
  - "Manager constructors preserve legacy selection inputs as inert outward-boundary configuration and never probe or initialize a driver."
  - "Network status and capability aggregation dispatches separate Wi-Fi and Bluetooth client actions; coexistence remains broker policy."
  - "Facade close is intentionally local so multiple managers can share one injected client and sole runtime owner."
patterns-established:
  - "Assert manager clean-break behavior with injected recording clients and AST import guards instead of hardware mocks."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Legacy Display, UPS, NFC, Storage, and Network manager names retain their constructors and public methods while dispatching only through an injected canonical client.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_manager_facades.py#test_manager_constructors_keep_legacy_inputs_without_initializing_hardware
        status: pass
      - kind: unit
        ref: tests/unit/test_manager_facades.py#test_every_manager_method_delegates_to_the_client
        status: pass
    human_judgment: false
  - id: D2
    description: Managers have no direct hardware-owner imports and facade close cannot close a shared client/runtime.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_manager_facades.py#test_manager_modules_import_no_hardware_owners
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
  - id: D3
    description: Radio compatibility keeps Wi-Fi and Bluetooth actions separate while preserving existing API behavior.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/test_radio_api.py
        status: pass
    human_judgment: false
metrics:
  duration: 8m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 27: Compatibility-Only Manager Facades Summary

**All historical hardware managers now remain thin, injected `LegacyHardwareClient` facades, with separate Wi-Fi/Bluetooth dispatch and no independent ownership path.**

## Performance

- **Duration:** 8m
- **Started:** 2026-08-26T16:06:06Z
- **Tasks:** 1/1
- **Files modified:** 10

## Accomplishments

- Replaced Display, UPS, NFC, Storage, and Network manager driver creation/initialization with compatibility-client delegates.
- Preserved legacy constructor inputs as inert outward-boundary configuration, and made each `close()` facade-local so shared injected clients and the sole runtime remain live.
- Added explicit canonical client action translations for display and radio status/capability operations; NetworkManager aggregates independent Wi-Fi and Bluetooth snapshots without coexistence policy.
- Added an exhaustive injected-client suite for every public manager constructor and method, local close behavior, and no-owner import boundaries.

## Task Commits

1. **Task 1: Delegate every manager method through the canonical client (RED)** — `3846a58` (`test`)
2. **Task 1: Delegate every manager method through the canonical client (GREEN)** — `8e61436` (`feat`)
3. **Integration repair: Replace stale direct-manager mock fixtures** — `cf219bc` (`test`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_manager_facades.py tests/unit/test_radio_api.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — passed (90 tests).
- `.venv/bin/python -m compileall -q src/totem/managers src/totem/compat` and `git diff --check` — passed.
- The AST/source ownership scan found no manager imports of `totem.devices`, built-in providers, or `DriverRegistry`, and no lifecycle, discovery, load, or restart calls.
- All checks used injected local fakes only; no SSH, network, live service, radio, device, USB/serial/I2C/GPIO, deployment, or hardware-marked test was contacted.
- `.venv/bin/python -m pytest tests/unit/test_mock_transports.py tests/unit/test_radio_primitives.py tests/unit/test_storage.py tests/unit/test_manager_facades.py tests/unit/test_radio_api.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — passed (142 tests).
- The non-hardware-marked full unit suite passed 425 tests before an unrelated order-sensitive Plan 01-28 Wi-Fi re-export identity assertion; its isolated suite passes (18 tests), and this repair leaves the Plan 01-28 code untouched.

## Files Created/Modified

- `src/totem/compat/hardware_client.py` — Extended canonical action translation for the remaining facade operations and independent radio snapshots.
- `src/totem/managers/{display_manager,ups_manager,nfc_manager,storage_manager,network_manager}.py` — Converted legacy managers into client-only adapters.
- `tests/unit/test_manager_facades.py` — Added exhaustive local compatibility, close, method-inventory, and import-boundary coverage.
- `tests/unit/{test_mock_transports,test_radio_primitives,test_storage}.py` — Replaced stale direct-manager mock fixtures with explicit stateful local client fakes.

## Decisions Made

- Preserve old driver-selection and mock/root inputs as inert `legacy_config` boundary data instead of using them to construct, probe, or select hardware locally.
- Keep caller-visible manager methods while routing NetworkManager through independent Wi-Fi/Bluetooth action families and leaving all admission/coexistence to the broker.
- Never close an injected canonical client from a manager facade; callers can safely share the application's one runtime-facing client.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Completed client action translations needed by the migrated manager methods**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** `LegacyHardwareClient` did not yet map the remaining display compatibility operations or independent Wi-Fi/Bluetooth snapshot calls, which would make default manager delegation fail with `AttributeError`.
- **Fix:** Added the needed operation-to-canonical-action mappings and changed network aggregation to dispatch distinct Wi-Fi and Bluetooth client operations.
- **Files modified:** `src/totem/compat/hardware_client.py`, `src/totem/managers/network_manager.py`.
- **Verification:** Manager facade, radio API, and import-boundary suites passed (90 tests).
- **Committed in:** `8e61436`.

**2. [Rule 1 - Bug] Repaired stale direct-manager mock transport fixtures**
- **Found during:** Post-plan non-hardware unit integration run.
- **Issue:** Mock transport, radio primitive, and storage tests still constructed managers without an injected client and asserted direct driver internals, causing `host_unavailable` failures and contradicting the facade-only contract.
- **Fix:** Replaced those fixtures with explicit stateful local client fakes and retained behavior-level assertions at the compatibility boundary.
- **Files modified:** `tests/unit/test_mock_transports.py`, `tests/unit/test_radio_primitives.py`, `tests/unit/test_storage.py`.
- **Verification:** The 142-test focused manager/mock/radio/storage/API/import suite passed; the original display mock transport failure is covered and passes.
- **Committed in:** `cf219bc`.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing critical functionality).
**Impact on plan:** Required for complete facade delegation and preserves the planned sole-runtime ownership architecture.

## Issues Encountered

The full non-hardware unit command reaches an unrelated order-sensitive Plan 01-28 Wi-Fi re-export identity assertion after 425 passing tests; running that test module alone passes all 18 tests. The Plan 01-28 code was not changed during this repair.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 28 can remove the remaining obsolete direct-driver compatibility assertions against these now client-only manager surfaces.
- No external contact occurred during this plan.

## TDD Gate Compliance

- RED `3846a58` failed during collection because managers did not accept an injected `client` seam.
- GREEN `8e61436` implemented the facade-only delegates and made the focused suite pass.

## Self-Check: PASSED

- Found every declared facade, client, and test file on disk.
- Found TDD commits `3846a58` and `8e61436` in git history.
- Found integration repair commit `cf219bc` in git history.
