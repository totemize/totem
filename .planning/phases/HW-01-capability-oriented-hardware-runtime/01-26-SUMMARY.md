---
phase: HW-01-capability-oriented-hardware-runtime
plan: "26"
subsystem: api-compatibility
tags: [python, fastapi, websocket, nip-5d, hardware-bus, compatibility]
requires:
  - phase: HW-01-23
    provides: One lifespan-scoped HardwareRuntime, opaque capability handles, and typed lifecycle events.
  - phase: HW-01-24
    provides: Loopback-protected canonical hardware bus and event projection.
  - phase: HW-01-25
    provides: Screen compatibility consumption through canonical capability ports.
provides:
  - Legacy REST, WebSocket, Python-client, and environment compatibility translators over the canonical hardware bus.
  - Loopback-protected canonical /bus and /bus/events routes sharing an injected runtime lifecycle.
  - Route, attachment, event, and import-boundary regression coverage using local injected fakes.
affects: [HW-01-27, HW-01-28, HW-01-32, compatibility, deployment]
tech-stack:
  added: []
  patterns:
    - Legacy manager-shaped calls are translated by LegacyHardwareClient into NIP-5D-shaped actions and raw attachments.
    - Runtime lifecycle events are projected to legacy WebSockets from the canonical stream, never produced by a facade queue.
key-files:
  created:
    - src/totem/compat/hardware_client.py
    - src/totem/compat/hardware_env.py
    - tests/unit/test_api_facades.py
  modified:
    - src/totem/api/app.py
    - src/totem/api/event_manager.py
    - src/totem/hardware/api/bus.py
    - tests/unit/test_service_api.py
    - tests/unit/test_radio_api.py
key-decisions:
  - "Legacy REST handlers retain their response models but delegate operations through one injected LegacyHardwareClient."
  - "Legacy environment names are read only by totem.compat.hardware_env and are converted to immutable typed inputs."
  - "The compatibility WebSocket projects the runtime event stream; canonical /bus and /bus/events remain peer-address loopback protected."
patterns-established:
  - "Use raw canonical attachments for decoded legacy binary input; base64 exists only at the compatibility route edge."
  - "Map stable canonical error codes to legacy HTTP statuses without exposing provider tracebacks."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Legacy API, Python, and environment surfaces translate into the canonical bus without constructing managers.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_service_api.py, tests/unit/test_radio_api.py, tests/unit/test_api_facades.py
        status: pass
    human_judgment: false
  - id: D2
    description: Canonical bus import boundary and loopback/event compatibility remain protected.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py, tests/unit/test_hardware_bus.py
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 26: API and Environment Compatibility Summary

**Deployed REST/WebSocket, Python-client, and environment surfaces now translate into bounded canonical bus actions while sharing one injected runtime owner.**

## Performance

- **Duration:** 25 min
- **Completed:** 2026-08-26
- **Tasks:** 1/1
- **Files modified:** 9

## Accomplishments

- Added `LegacyHardwareClient` and typed `hardware_env` translation so deployed callers never instantiate a manager, registry, provider, or runtime.
- Rewired all legacy route handlers through that adapter, preserving response models, stable error statuses, and raw canonical binary attachments at the base64 edge.
- Kept `/bus` and `/bus/events` loopback-only on the injected runtime and projected the same runtime event stream to the legacy WebSocket.
- Added route-inventory, service/radio, event-projection, attachment, and import-boundary tests using only local in-process fakes.

## Task Commits

1. **Task 1: Translate every deployed API route and event stream into bus messages** — `afd11ef` (TDD RED), `15655d2` (GREEN), `089fbf5` (event-projection correction).

## Files Created/Modified

- `src/totem/compat/hardware_client.py` — manager-shaped compatibility calls to typed canonical actions.
- `src/totem/compat/hardware_env.py` — sole typed boundary for legacy `TOTEM_*` values.
- `src/totem/api/app.py` — legacy REST routes, canonical loopback routes, and one runtime lifespan.
- `src/totem/api/event_manager.py` — legacy WebSocket projection of canonical runtime events.
- `src/totem/hardware/api/bus.py` — capability routing for compatibility action families.
- `tests/unit/test_api_facades.py` — exhaustive route and compatibility-boundary contract.

## Decisions Made

- The adapter exposes historical operation shapes but dispatches semantic capability action names, so API callers cannot regain direct driver ownership.
- Runtime events are bridged from `RuntimeEventStream`; no manager callback or independently authored API event source remains in the injected-runtime path.
- Decoded display and binary values become bounded raw `_attachments` before they enter canonical dispatch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the UPS action identity and runtime-event projection import**
- **Found during:** Task 1
- **Issue:** Generic `get_status` selected the radio action for UPS telemetry, and the initial runtime event projection lacked the `DeviceId` import.
- **Fix:** Added an explicit `get_ups_status` compatibility operation and completed the runtime event projection import.
- **Files modified:** `src/totem/api/app.py`, `src/totem/api/event_manager.py`, `src/totem/compat/hardware_client.py`
- **Verification:** Focused API, event, canonical bus, and import-boundary tests pass.
- **Committed in:** `089fbf5` (with the planned event projection correction)

**Total deviations:** 1 auto-fixed (Rule 1 bug).
**Impact on plan:** Required for correct telemetry routing and WebSocket runtime-event delivery; no scope expansion.

## Known Stubs

None.

## Issues Encountered

The initial event-projection test exposed a subscription startup race; it was made deterministic with a bounded local wait before publishing the injected runtime event.

## User Setup Required

None — verification used local ASGI/test clients and injected fakes only.

## Next Phase Readiness

- Compatibility routes now have one canonical ownership path for later deployment and final-regression plans.
- Future provider implementations must accept the published semantic action names and preserve the stable result shapes at this outward boundary.

## Self-Check: PASSED

- Created compatibility modules and facade regression test exist.
- Task commits `afd11ef`, `15655d2`, and `089fbf5` exist in repository history.
- No stub, skipped-test, or unrun-verification markers were found in plan-modified files.
