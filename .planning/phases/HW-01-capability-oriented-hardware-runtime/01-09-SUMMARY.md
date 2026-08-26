---
phase: HW-01-capability-oriented-hardware-runtime
plan: "09"
subsystem: hardware-runtime
tags: [python, lifecycle, process-supervision, resource-leases, fault-injection, ipc]
requires:
  - phase: HW-01-07
    provides: Generation- and token-bound atomic resource leases
  - phase: HW-01-08
    provides: Generation-scoped logical IPC and bounded Unix framing
provides:
  - Explicit immutable binding lifecycle, health snapshots, and ordered event stream
  - Provider-default process grouping with generation-bound readiness and request routing
  - Confirmed-exit lease release, bounded recovery backoff, and quarantine telemetry
affects: [in-process-host, runtime-composition, hardware-bus, capability-services]
tech-stack:
  added: []
  patterns: [explicit transition table, immutable reconcileable snapshots, confirmed-death release ordering, fake-clock fault injection]
key-files:
  created:
    - packages/totem-driver-api/src/totem_driver_api/lifecycle.py
    - src/totem/hardware/runtime/lifecycle.py
    - src/totem/hardware/runtime/events.py
    - src/totem/hardware/runtime/supervisor.py
    - src/totem/hardware/hosts/base.py
    - tests/unit/hardware_runtime/test_lifecycle.py
    - tests/unit/hardware_runtime/test_process_host.py
  modified:
    - packages/totem-driver-api/src/totem_driver_api/__init__.py
    - src/totem/hardware/hosts/process.py
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/runtime/__init__.py
key-decisions:
  - "Lifecycle is explicit and locked; required readiness is derived separately from optional binding degradation."
  - "Process recovery releases a generation only after invalidate, terminate/kill, confirmed wait, and carrier closure."
  - "Provider distribution plus version is the default failure domain; manifest grouping='binding' is an explicit override."
patterns-established:
  - "Use a generation-bound host.ready handshake before publishing a binding handle or accepting a correlated result."
  - "Use fake hosts, clocks, and broker records to prove timeout, kill escalation, stale-result rejection, backoff, and quarantine without hardware."
requirements-completed: [ISO-01, ISO-05, ISO-07, RUN-01]
coverage:
  - id: D1
    description: Explicit lifecycle transitions, immutable health snapshots, ordered lossy events, required/optional readiness, and idempotent empty close.
    requirement: RUN-01
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py -x
        status: pass
    human_judgment: false
  - id: D2
    description: Isolated provider grouping, generation-aware readiness/routing, confirmed-death recovery, backoff, and quarantine.
    requirement: ISO-01
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py -x
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime -x
        status: pass
    human_judgment: false
  - id: D3
    description: Process host avoids daemon provider imports and shell spawning while carrying session/generation identity.
    requirement: ISO-07
    verification:
      - kind: other
        ref: Source audit of runtime supervisor/events/lifecycle and ProcessDriverHost imports/spawn options
        status: pass
    human_judgment: false
metrics:
  duration: 40m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 09: Explicit Lifecycle and Process Supervision Summary

**The hardware runtime now exposes an explicit lifecycle and uses generation-aware process supervision that proves child death before releasing resource leases.**

## Performance

- **Duration:** 40m
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- Added public `BindingState`, `HealthState`, and immutable `LifecycleEvent` contracts, locked binding transition records, reconcileable runtime snapshots, and monotonic lossy subscriber events.
- Added provider-version process grouping with a per-binding override, ready-handshake validation, session/generation request routing, startup and operation deadline paths, and safe public fault codes.
- Added the exact recovery order: invalidate correlations, terminate, escalate to kill, confirm exit, close the carrier, release leases, back off, reacquire, and publish only a ready replacement generation.
- Added fake-backed fault injection for startup timeout, hard hang, stale result, group selection, bounded backoff, and quarantine; no test contacted hardware or a device.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_process_host.py -x` — passed (9 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (88 tests).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (224 tests).
- `.venv/bin/python -m compileall -q packages/totem-driver-api/src/totem_driver_api src/totem/hardware/runtime src/totem/hardware/hosts` — passed.
- `git diff --check` — passed.
- Source audit found no provider import/dynamic import, `multiprocessing`, `pickle`, or shell-spawn pattern in supervisor/lifecycle/event parent modules or `ProcessDriverHost`.

## TDD Gate Compliance

- RED `30490a7` added the lifecycle contract and failed because the public lifecycle module was absent.
- GREEN `bd3988f` implemented explicit transitions, health, events, immutable snapshots, and host-first close.
- RED `1897368` added the process fault-injection contract and failed because the supervisor module was absent.
- GREEN `2efdcaf` implemented grouped process supervision, confirmed-exit lease release, and bounded recovery.

## Task Commits

1. **Task 1: Enforce explicit lifecycle, health snapshots, and ordered events** — `30490a7` (RED), `bd3988f` (GREEN)
2. **Task 2: Supervise external provider groups through confirmed-exit recovery** — `1897368` (RED), `2efdcaf` (GREEN)

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/lifecycle.py` — public lifecycle vocabulary and immutable events.
- `src/totem/hardware/runtime/lifecycle.py` and `events.py` — locked state machine, health projection, snapshots, and bounded subscribers.
- `src/totem/hardware/runtime/supervisor.py` — grouping, deadline/recovery policy, generation routing, quarantine, and lease-safe cleanup.
- `src/totem/hardware/hosts/base.py`, `process.py`, and `worker.py` — shared host port plus generation-bound grouped child handshake and dispatch.
- `tests/unit/hardware_runtime/test_lifecycle.py` and `test_process_host.py` — deterministic lifecycle and fake-process fault-injection coverage.

## Decisions Made

- A failed optional binding degrades aggregate health without failing required readiness; a failed required binding prevents ready status.
- A group becomes quarantined after five failures in the configured window and only an explicit controlled restart clears it.
- Lifecycle and supervisor diagnostics expose state, generation, restart count, exit status, process group, and held leases, never provider tracebacks, tokens, or secret values.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected idempotent-close re-entry deadlock**
- **Found during:** Task 1 lifecycle verification.
- **Issue:** The closed-runtime fast path re-entered a non-reentrant lock while reconstructing its snapshot.
- **Fix:** Used a reentrant lifecycle lock so repeated `close()` is deterministic and non-blocking.
- **Files modified:** `src/totem/hardware/runtime/lifecycle.py`.
- **Verification:** Lifecycle and full unit suites pass.
- **Committed in:** `2efdcaf`.

**2. [Rule 2 - Correctness] Made aggregate snapshots and event snapshots fully immutable**
- **Found during:** Task 2 source review.
- **Issue:** Binding records were frozen but the aggregate binding map and event snapshot attachment could still be mutated indirectly.
- **Fix:** Wrapped aggregate mappings and event details in immutable projections and made the snapshot an explicit frozen event field.
- **Files modified:** `packages/totem-driver-api/src/totem_driver_api/lifecycle.py`, `src/totem/hardware/runtime/lifecycle.py`, `src/totem/hardware/runtime/events.py`, `tests/unit/hardware_runtime/test_lifecycle.py`.
- **Verification:** Lifecycle immutability assertions and full unit suite pass.
- **Committed in:** `2efdcaf`.

**3. [Rule 2 - Security] Reject unknown binding IDs before worker dispatch**
- **Found during:** Task 2 child-dispatch source audit.
- **Issue:** An invalid binding identifier was converted to an error after provider dispatch had already begun.
- **Fix:** Validate worker binding membership before invoking the provider.
- **Files modified:** `src/totem/hardware/hosts/worker.py`.
- **Verification:** Process-host and full hardware-runtime suites pass; source audit confirms parent/provider boundary remains intact.
- **Committed in:** `2efdcaf`.

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 2 correctness/security). **Impact:** All changes are required for safe lifecycle semantics and do not expand the planned architecture.

## Known Stubs

None.

## Threat Flags

None. The worker/supervisor boundary was planned and covered by the phase threat model; no additional network, authentication, file-access, or schema trust boundary was introduced.

## User Setup Required

None — all verification is local, uses `.venv/bin/python`, and does not require device, SSH, deployment, network, or hardware access.

## Next Phase Readiness

The in-process host plan can implement the same `DriverHost` contract while retaining its distinct contamination/lease semantics. Runtime composition can now consume explicit health, lifecycle events, group generations, and deterministic supervisor recovery state.

## Self-Check: PASSED

- All seven created implementation/test files and modified host/API files exist in the worktree.
- RED/GREEN commits `30490a7`, `bd3988f`, `1897368`, and `2efdcaf` exist in git history.
- No plan-blocking stubs, skipped tests, or unrun verification commands remain.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
