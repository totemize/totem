---
phase: HW-01-capability-oriented-hardware-runtime
plan: "23"
subsystem: hardware-runtime
tags: [python, capability-handles, lifecycle, health, events, resource-leases, pytest]
requires:
  - phase: HW-01-09
    provides: Explicit lifecycle, generation-aware supervision, and safe confirmed-release ordering.
  - phase: HW-01-22
    provides: Independent lease-gated built-in Bluetooth provider and dual-host contract conventions.
provides:
  - One eager HardwareRuntime owner for an immutable binding plan, broker, supervisor set, health, and lifecycle events.
  - Transport-neutral opaque capability and family handles gated by binding readiness and identity.
  - Redacted typed runtime health and deterministic local composition coverage.
affects: [HW-01-24, hardware-api, runtime-composition, capability-services]
tech-stack:
  added: []
  patterns:
    - A lifespan-scoped runtime is the only owner of binding hosts; applications receive opaque capability handles.
    - Supervisor failure state is reflected into typed lifecycle health before a handle can be used again.
key-files:
  created:
    - src/totem/hardware/runtime/runtime.py
    - src/totem/hardware/runtime/health.py
    - src/totem/hardware/capabilities/base.py
    - src/totem/hardware/capabilities/power.py
    - src/totem/hardware/capabilities/storage.py
    - src/totem/hardware/capabilities/nfc.py
    - src/totem/hardware/capabilities/radio/wifi.py
    - src/totem/hardware/capabilities/radio/bluetooth.py
    - tests/unit/hardware_runtime/test_runtime.py
  modified:
    - src/totem/hardware/runtime/__init__.py
    - src/totem/hardware/runtime/events.py
    - src/totem/hardware/capabilities/__init__.py
    - src/totem/hardware/capabilities/display.py
key-decisions:
  - "One runtime is registered per explicit lifespan object and releases that ownership only after confirmed clean shutdown."
  - "Public handles contain only capability and binding identities plus a runtime dispatch seam; provider and driver objects never escape."
  - "Runtime health projects typed lifecycle data without leases, tokens, config values, tracebacks, or concrete provider objects."
patterns-established:
  - "Start groups in deterministic binding order, publish handles only after host.ready, and convert supervisor faults into lifecycle health state."
requirements-completed: [HWR-04]
coverage:
  - id: D1
    description: One eager runtime owns the immutable plan, broker-backed supervisors, lifecycle, health, and lifespan guard.
    requirement: HWR-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_runtime.py#test_runtime_is_one_eager_owner_with_capability_handles_and_clean_shutdown
        status: pass
    human_judgment: false
  - id: D2
    description: Required and optional startup semantics, quarantine, and handle unavailability are deterministic and transport-independent.
    requirement: HWR-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_runtime.py
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_in_process_host.py
        status: pass
    human_judgment: false
metrics:
  duration: 10m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 23: Eager Runtime Ownership and Capability Handles Summary

**A single eager HardwareRuntime now owns the immutable capability plan, broker-backed host supervisors, typed health/events, and opaque family handles for the full application lifespan.**

## Performance

- **Duration:** 10m
- **Tasks:** 1/1
- **Files modified:** 14

## Accomplishments

- Added the transport-independent `HardwareRuntime` that eagerly starts deterministic binding groups, enforces one owner per lifespan, and closes supervisors before releasing ownership.
- Added redacted `RuntimeHealth` projections and public lifecycle event aliases that expose no secret, lease token, provider object, or concrete driver/model type.
- Added generic capability handles plus display, power, storage, NFC, Wi-Fi, and Bluetooth family handle types; handles reject identity mismatches and unavailable, quarantined, contaminated, or closed work.
- Added injected-host tests for eager startup, required-versus-optional readiness, handle dispatch/invalidation, quarantine, clean release, and no live local resource ownership.

## Task Commits

1. **Task 1: Compose one eager runtime owner and stable handles (RED)** — `f2a027f` (`test`)
2. **Task 1: Compose one eager runtime owner and stable handles (GREEN)** — `ed7fec8` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py -x` — passed (3 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_in_process_host.py -x` — passed (15 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — passed (14 tests).
- `.venv/bin/python -m compileall -q src/totem/hardware/runtime src/totem/hardware/capabilities` and `git diff --check` — passed.
- All verification used deterministic injected hosts, local unit seams, and mocked resources only; no device, network, radio, D-Bus service, USB/serial/I2C/GPIO, deployment, or hardware-marked test was contacted.

## Files Created/Modified

- `src/totem/hardware/runtime/runtime.py` — Sole eager composition owner, lifecycle-to-supervisor coordination, handle factory, and close ordering.
- `src/totem/hardware/runtime/health.py` — Immutable, typed, redacted runtime and binding health projections.
- `src/totem/hardware/runtime/{events.py,__init__.py}` — Public runtime event and composition exports.
- `src/totem/hardware/capabilities/{base.py,display.py,power.py,storage.py,nfc.py}` — Generic and family-neutral application handles.
- `src/totem/hardware/capabilities/radio/{wifi.py,bluetooth.py}` — Opaque radio family handles.
- `tests/unit/hardware_runtime/test_runtime.py` — Fully local eager ownership, readiness, quarantine, dispatch, and cleanup proof.

## Decisions Made

- Bind runtime ownership to an explicit lifespan object, retaining it through a contaminated state so a second runtime cannot falsely replace live in-process work.
- Preserve the existing `DisplayHandle(binding_id, host)` compatibility path while allowing runtime-owned handle dispatch through the generic capability contract.
- Treat only required bindings as readiness gates; optional startup failure remains visible as degraded health and never publishes a handle.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 24 can attach loopback bus, health, and SSE transport through the public `HardwareRuntime.handle`, `health`, and `events` seams without adding a second hardware owner.
- No external contact occurred during this plan.

## TDD Gate Compliance

- RED `f2a027f` failed during collection because `CapabilityUnavailable` and the runtime module did not yet exist.
- GREEN `ed7fec8` implemented the runtime composition and made the focused runtime suite pass.

## Self-Check: PASSED

- Found every declared runtime, health, handle, and focused test file on disk.
- Found TDD commits `f2a027f` and `ed7fec8` in git history.
