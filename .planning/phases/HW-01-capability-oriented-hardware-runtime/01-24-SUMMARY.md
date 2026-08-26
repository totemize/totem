---
phase: HW-01-capability-oriented-hardware-runtime
plan: "24"
subsystem: hardware-api
tags: [python, fastapi, nip-5d, sse, loopback, capability-handles, lifecycle]
requires:
  - phase: HW-01-23
    provides: One eager HardwareRuntime owner with opaque handles, typed health, and lifecycle events.
  - phase: HW-01-08
    provides: Bounded strict-JSON THW1 carrier with raw attachment integrity.
provides:
  - Correlated loopback-only NIP-5D request/result dispatch through runtime handles.
  - Redacted runtime health and typed lossy lifecycle SSE projections.
  - Observable slow-consumer event drops without a parallel hardware owner.
affects: [HW-01-25, HW-01-26, hardware-api, capability-applications]
tech-stack:
  added: []
  patterns: [peer-address loopback gate, lifespan-scoped sole runtime, redacted typed SSE]
key-files:
  created:
    - src/totem/hardware/api/events.py
    - src/totem/hardware/api/health.py
    - tests/unit/test_hardware_bus.py
  modified:
    - src/totem/hardware/api/app.py
    - src/totem/hardware/api/bus.py
    - src/totem/hardware/runtime/events.py
key-decisions:
  - "The loopback gate trusts only the ASGI peer address, never forwarded headers."
  - "The application owns exactly one injected or factory-created runtime for its lifespan; the legacy handle-map bus is migration-only."
  - "SSE drops stale entries for slow consumers and exposes only aggregate drop count plus redacted typed lifecycle values."
patterns-established:
  - "Resolve a message through the runtime's capability and binding handle before dispatch; provider objects remain inaccessible to transport."
requirements-completed: [API-01]
coverage:
  - id: D1
    description: Correlated capability-handle bus dispatch with bounded attachments and safe errors.
    requirement: API-01
    verification:
      - kind: unit
        ref: tests/unit/test_hardware_bus.py#test_bus_correlates_requests_rejects_unknown_pushes_and_bounds_attachments
        status: pass
    human_judgment: false
  - id: D2
    description: Loopback-only health and SSE routes over exactly one runtime lifespan.
    requirement: API-01
    verification:
      - kind: unit
        ref: tests/unit/test_hardware_bus.py#test_app_lifespan_uses_one_injected_runtime_and_rejects_spoofed_peers
        status: pass
    human_judgment: false
  - id: D3
    description: Ordered, typed, redacted lossy SSE projection with observable backpressure.
    requirement: API-01
    verification:
      - kind: unit
        ref: tests/unit/test_hardware_bus.py#test_sse_projection_is_typed_ordered_lossy_and_redacted
        status: pass
    human_judgment: false
metrics:
  duration: 24m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 24: Runtime-Owned Loopback Bus Summary

**A single runtime now powers a correlated NIP-5D hardware bus, redacted health, and lossy typed lifecycle SSE behind peer-enforced loopback routes.**

## Performance

- **Duration:** 24m
- **Tasks:** 1/1
- **Files modified:** 7

## Accomplishments

- Reworked `HardwareBus` to resolve canonical requests through runtime capability/binding handles, correlate successes and errors by ID, ignore uncorrelated pushes, and retain carrier attachment limits.
- Added a FastAPI lifespan that starts and closes exactly one injected or explicit-factory runtime, with peer-address loopback enforcement on `/bus`, `/health`, and `/bus/events` that cannot be bypassed by forwarded headers.
- Added redacted health and typed lifecycle SSE projections, including bounded newest-state delivery and aggregate slow-consumer drop visibility.
- Added fully local ASGI/unit coverage for correlation, invalid routing, bounds, single ownership, spoof resistance, health, SSE ordering, redaction, and backpressure.

## Verification

- `.venv/bin/python -m pytest tests/unit/test_hardware_bus.py -x` — passed (3 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py tests/unit/hardware_runtime/test_runtime_tracer.py -x` — passed (5 tests).
- `.venv/bin/python -m compileall -q src/totem/hardware/api src/totem/hardware/runtime` and `git diff --check` — passed.
- Full `tests/unit` regression reached 206 passed tests before the known Plan 01-28 legacy `DeviceDriver` migration-window assertion failed; it is logged in `deferred-items.md` and was not changed by this plan.
- All verification used injected hosts and in-process ASGI clients only; no device, SSH, network, radio, service, deployment, or hardware-marked test was contacted.

## TDD Gate Compliance

- RED `219f54d` added the runtime-backed bus, loopback, health, and SSE specification; it failed because `HardwareBus` only accepted a legacy display-handle map.
- GREEN `c2686ed` implemented the runtime façade and made the focused and regression suites pass.

## Task Commits

1. **Task 1 RED: Specify loopback request/result, health, and typed SSE** — `219f54d` (`test`)
2. **Task 1 GREEN: Complete loopback request/result, health, and typed SSE** — `c2686ed` (`feat`)

## Files Created/Modified

- `src/totem/hardware/api/{app.py,bus.py}` — sole-runtime lifespan, peer-address guard, bounded correlated dispatch, and legacy tracer compatibility.
- `src/totem/hardware/api/{health.py,events.py}` — safe health JSON and typed SSE lifecycle projection.
- `src/totem/hardware/runtime/events.py` — subscriber removal and aggregate lossy-delivery counter.
- `tests/unit/test_hardware_bus.py` — deterministic local transport and backpressure coverage.

## Decisions Made

- Peer identity is the ASGI connection peer rather than a forwarded request header, so a broad inherited listener cannot be spoofed into serving the local bus.
- The app accepts one injected runtime or an explicit construction factory and never creates a second runtime during lifespan entry.
- SSE can lose stale events by design; consumers reconcile through health, while the aggregate dropped-event counter makes pressure visible without disclosing payloads.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Expose lossy SSE backpressure from the runtime event stream**
- **Found during:** Task 1 GREEN.
- **Issue:** The existing bounded stream dropped stale subscriber entries but did not expose that loss, leaving the planned SSE backpressure behavior unobservable.
- **Fix:** Added aggregate dropped-event telemetry and explicit unsubscription to `RuntimeEventStream`; the API projection exposes only the count.
- **Files modified:** `src/totem/hardware/runtime/events.py`, `src/totem/hardware/api/events.py`, `tests/unit/test_hardware_bus.py`.
- **Verification:** Focused bus, runtime, and tracer tests passed.
- **Committed in:** `c2686ed`.

**Total deviations:** 1 auto-fixed (Rule 2 missing critical functionality). **Impact:** Completes the required lossy-but-observable SSE contract without adding a new runtime, provider, or external transport.

## Issues Encountered

- The full unit regression failed after 206 passes on the pre-existing `mock_eink` legacy `DeviceDriver` inheritance assertion. It is already assigned to Plan 01-28; `deferred-items.md` records it rather than restoring prohibited legacy ownership.

## Known Stubs

None.

## Threat Flags

None — the new HTTP/SSE trust surface is planned and is protected by peer-derived loopback enforcement, bounded attachments/queues, and typed redacted projections.

## Next Phase Readiness

Plan 25 can consume the canonical application surface without creating parallel hardware state. The legacy full-unit migration-window assertion remains deferred to Plan 01-28.

## Self-Check: PASSED

- Found all declared API, runtime-event, and focused test files.
- Found RED and GREEN commits `219f54d` and `c2686ed` in git history.
