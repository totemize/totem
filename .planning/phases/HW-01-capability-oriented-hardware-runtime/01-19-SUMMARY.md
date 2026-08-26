---
phase: HW-01-capability-oriented-hardware-runtime
plan: "19"
subsystem: hardware-radio-contracts
tags: [radio, wifi, bluetooth, resource-lease, compatibility-policy, dbus, pytest]
requires:
  - phase: HW-01-07
    provides: Atomic generic resource claims and compatibility-group metadata.
  - phase: HW-01-18
    provides: Built-in provider ownership and deterministic injected-test patterns.
provides:
  - Separate backend-free Wi-Fi and Bluetooth public capability contracts.
  - Explicit radio resource constraints and deterministic shared-PHY coexistence enforcement.
  - Provider-side injected D-Bus support, stable errors, and data-only service models.
affects: [HW-01-20, HW-01-21, radio-providers, runtime-broker]
tech-stack:
  added: []
  patterns:
    - Radio providers express PHY, interface, adapter, mode, and compatibility group as generic broker claims.
    - Optional broker policies validate a complete active-plus-requested binding set before lease mutation.
key-files:
  created:
    - packages/totem-driver-api/src/totem_driver_api/capabilities/radio/wifi.py
    - packages/totem-driver-api/src/totem_driver_api/capabilities/radio/bluetooth.py
    - src/totem/hardware/capabilities/radio/shared.py
    - src/totem/hardware/builtin/radio/dbus_runtime.py
    - tests/unit/hardware_runtime/test_radio_resources.py
    - tests/unit/hardware_runtime/test_radio_shared_support.py
  modified:
    - src/totem/hardware/runtime/broker.py
key-decisions:
  - "Wi-Fi and Bluetooth publish separate major-versioned data contracts; backend sessions remain a later provider concern."
  - "Radio coexistence is an explicit symmetric matrix scoped to matching PHY and compatibility group, so independent radios never contend through a global lock."
  - "Provider-side D-Bus support accepts an injected call seam and names services only; it owns neither a bus connection nor a backend session."
patterns-established:
  - "A broker compatibility policy receives all active and requested bindings under the existing atomic broker lock, then either admits the whole set or rejects it before any lease state changes."
requirements-completed: [API-02, RUN-03]
coverage:
  - id: D1
    description: Wi-Fi and Bluetooth have backend-free, versioned action/result/push value contracts.
    requirement: API-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_radio_resources.py#test_public_wifi_and_bluetooth_contracts_are_narrow_and_json_data_only
        status: pass
    human_judgment: false
  - id: D2
    description: Shared-PHY radio mode compatibility is deterministic, admits independent PHYs, and rejects incompatible combinations before broker lease mutation.
    requirement: RUN-03
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_radio_resources.py
        status: pass
    human_judgment: false
  - id: D3
    description: Provider-side D-Bus support is recursive data normalization over an injected local call seam with no system-bus ownership.
    requirement: API-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_radio_shared_support.py
        status: pass
    human_judgment: false
duration: 15min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 19: Radio Contracts and Coexistence Summary

**Separate `wifi.connection@1` and `bluetooth.session@1` data contracts now share an explicit, deterministic radio-resource coexistence policy and injected provider-side D-Bus support.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-26T14:05:00Z
- **Completed:** 2026-08-26T14:20:23Z
- **Tasks:** 1/1
- **Files modified:** 13

## Accomplishments

- Added narrow Wi-Fi and Bluetooth action, result, and push values without NetworkManager, BlueZ, or D-Bus backend classes in the public driver API.
- Added `RadioConstraint` generic PHY/interface/adapter/mode/group claims and a symmetric coexistence matrix that is checked before broker lease state mutates.
- Added provider-side service/error/model support and an injected `DBusRuntime` seam; all tests use local call recorders only.

## Task Commits

1. **Task 1: Publish radio contracts, shared support, and coexistence policy (RED)** — `a552b09` (`test`)
2. **Task 1: Publish radio contracts, shared support, and coexistence policy (GREEN)** — `ff99cde` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_radio_resources.py tests/unit/hardware_runtime/test_radio_shared_support.py -x` — 15 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_broker.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 14 passed.
- `compileall` for public radio contracts, runtime coordination, provider support, and broker — passed.
- Public-API backend-name audit and `git diff --check` — passed.

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/capabilities/radio/` — Separate immutable Wi-Fi and Bluetooth contract values.
- `src/totem/hardware/capabilities/radio/shared.py` — Generic radio claims and deterministic compatibility matrix.
- `src/totem/hardware/runtime/broker.py` — Optional policy hook evaluated before lease mutation.
- `src/totem/hardware/builtin/radio/` — Backend-neutral D-Bus seam, service model, and public radio errors.
- `tests/unit/hardware_runtime/test_radio_resources.py` and `test_radio_shared_support.py` — Fixture-only contract, concurrency, and injection coverage.

## Decisions Made

- Version Wi-Fi and Bluetooth independently as separate capabilities; Plan 20 can implement Wi-Fi sessions without reopening the Bluetooth public boundary.
- Scope coexistence by matching PHY and compatibility group, allowing independent adapters to proceed concurrently.
- Keep D-Bus invocation injected and provider-side so importing shared support cannot contact a privileged system service.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the TDD capability identity assertion**
- **Found during:** Task 1 GREEN verification.
- **Issue:** The initial RED specification compared `CapabilityId`'s debug representation instead of its established `name` and `major` fields.
- **Fix:** Asserted the existing stable `name`/`major` API, retaining the intended version-boundary coverage.
- **Files modified:** `tests/unit/hardware_runtime/test_radio_resources.py`
- **Verification:** Focused radio suite passed 15 tests.
- **Committed in:** `ff99cde` (part of Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The correction keeps the new contract test aligned with the public API and adds no production scope.

## Issues Encountered

None.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 20 can add concrete Wi-Fi sessions against a fixed public boundary and generic resource policy.
- No device, SSH, network, D-Bus service, radio, GPIO, USB, serial, I2C, or hardware-marked test was contacted.

## Self-Check: PASSED

- Found all public contract, shared coordination, provider-support, and fixture-test files on disk.
- Found TDD commits `a552b09` and `ff99cde` in git history.
