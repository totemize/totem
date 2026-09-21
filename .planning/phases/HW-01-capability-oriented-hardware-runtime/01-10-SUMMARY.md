---
phase: HW-01-capability-oriented-hardware-runtime
plan: "10"
subsystem: hardware-runtime
tags: [python, driver-hosts, in-process, conformance, cancellation, lifecycle]
requires:
  - phase: HW-01-09
    provides: Generation-aware process supervision and confirmed-exit resource-lease semantics
provides:
  - Explicit opt-in in-process DriverHost with cooperative cancellation and truthful contamination
  - Global, plugin, binding, and manifest-default host mode precedence with process as the default
  - Dependency-free reusable conformance transcripts proven against both host modes
affects: [runtime-composition, health-projection, driver-providers, capability-services]
tech-stack:
  added: []
  patterns: [shared frame-codec boundary, cooperative cancellation followed by liveness decision, containment telemetry outside functional transcript]
key-files:
  created:
    - src/totem/hardware/hosts/in_process.py
    - packages/totem-driver-api/src/totem_driver_api/conformance/suite.py
    - tests/unit/hardware_runtime/test_in_process_host.py
    - tests/unit/hardware_runtime/test_conformance.py
  modified:
    - src/totem/hardware/runtime/supervisor.py
    - src/totem/hardware/runtime/config.py
    - src/totem/hardware/hosts/process.py
    - packages/totem-driver-api/src/totem_driver_api/__init__.py
key-decisions:
  - "In-process calls round-trip through the existing strict frame codec before direct dispatch, so they do not create a second logical contract."
  - "A live invocation after cancellation grace contaminates its group, removes its route, retains every lease, and requires controlled daemon restart; Python threads are never claimed killed."
  - "Functional conformance strips only generation and fixture-import diagnostics while retaining the exact order of transcript items."
patterns-established:
  - "Use RuntimeConfig.execution_mode for binding > plugin > global > manifest host selection; process remains the implicit default."
  - "Cache a verified process host.ready result so lifecycle/conformance startup checks are idempotent."
requirements-completed: [ISO-02, ISO-06, TST-01]
coverage:
  - id: D1
    description: Opt-in in-process host validates the shared envelope, signals cooperative cancellation, and contaminates live code without releasing its leases.
    requirement: ISO-06
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -x
        status: pass
    human_judgment: false
  - id: D2
    description: Public conformance helpers compare ordered logical transcripts across the local process and in-process hosts while retaining host-specific containment telemetry.
    requirement: TST-01
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py tests/unit/hardware_runtime/test_in_process_host.py -x
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime -x
        status: pass
    human_judgment: false
  - id: D3
    description: Process remains the default execution mode and in-process selection is resolved from binding, plugin, global, then manifest configuration.
    requirement: ISO-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_in_process_host.py#test_host_mode_selection_is_binding_then_plugin_then_global_then_manifest_default
        status: pass
    human_judgment: false
metrics:
  duration: 31m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 10: In-Process Host and Dual-Host Conformance Summary

**Totem now supports explicit, same-contract in-process drivers with cooperative cancellation, contamination-safe lease retention, and reusable process/in-process transcript conformance.**

## Performance

- **Duration:** 31m
- **Tasks:** 2/2
- **Files modified:** 11

## Accomplishments

- Added `InProcessDriverHost`, which applies the same bounded frame codec and worker dispatch path as process hosts before calling a selected provider.
- Added cancellation grace/liveness handling: cooperative work returns to `READY`; still-live work becomes `CONTAMINATED`, is rejected from routing, retains leases, and reports restart-required without pretending its thread stopped.
- Added deterministic host-mode selection with binding > plugin > global > manifest precedence and a default of `process`.
- Published dependency-free conformance fixtures/runners in `totem_driver_api`, and compared real local process-host and in-process transcript order without normalizing containment semantics away.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py tests/unit/hardware_runtime/test_in_process_host.py -x` — passed (6 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (94 tests).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (230 tests).
- `.venv/bin/python -m compileall -q packages/totem-driver-api/src/totem_driver_api src/totem/hardware/runtime src/totem/hardware/hosts` — passed.
- `git diff --check` — passed.
- Public-API source audit found no Totem runtime, FastAPI, or manager imports in `totem_driver_api.conformance`; host source audit found no thread-kill, pickle, or subprocess implementation in the in-process adapter.

## TDD Gate Compliance

- RED `b007de8` added the failing in-process cancellation/contamination and configuration-precedence contract.
- GREEN `60f9851` implemented the host, supervisor contamination path, and config selection.
- RED `5620c20` added the failing public dual-host conformance contract.
- GREEN `b805d87` published the reusable API and real local process/in-process comparison.

## Task Commits

1. **Task 1: Execute the shared protocol in process with cooperative cancellation** — `b007de8` (RED), `60f9851` (GREEN)
2. **Task 2: Publish and run one reusable conformance suite against both hosts** — `5620c20` (RED), `b805d87` (GREEN), `637b0b7` (fix)

## Files Created/Modified

- `src/totem/hardware/hosts/in_process.py` — cooperative-only, contamination-aware host adapter.
- `src/totem/hardware/runtime/supervisor.py` — prevents contaminated groups from releasing leases or being replaced.
- `src/totem/hardware/runtime/config.py` — explicit host-mode precedence seam.
- `packages/totem-driver-api/src/totem_driver_api/conformance/` — portable fixture protocol and ordered transcript runner.
- `tests/unit/hardware_runtime/test_in_process_host.py` and `test_conformance.py` — local fault and real dual-host proofs.

## Decisions Made

- Process mode remains default; in-process is always a validated explicit configuration choice.
- A timed-out Python thread is an observable live invocation, not a stopped thread. Contamination is terminal for that daemon lifetime.
- Functional message ordering is strict; only non-functional generation and fixture-import diagnostics are excluded from transcript comparisons.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Isolated an in-process fixture import marker from later package-boundary tests**
- **Found during:** Task 2 full hardware-runtime verification.
- **Issue:** The deliberately imported fixture sets `TOTEM_DRIVER_FIXTURE_IMPORTED`; its test process inherited that marker into a later independent-wheel source-audit check.
- **Fix:** Cleared the marker in `finally` after the dual-host conformance proof.
- **Files modified:** `tests/unit/hardware_runtime/test_conformance.py`.
- **Verification:** The 94-test hardware-runtime and 230-test full unit suites pass.
- **Committed in:** `637b0b7`.

**Total deviations:** 1 auto-fixed (1 Rule 1 bug). **Impact:** Test isolation only; no runtime scope expansion.

## Known Stubs

None.

## Threat Flags

None. The explicit in-process third-party-code boundary, cancellation/liveness control, and telemetry are the planned SEC-08 boundary; no unplanned network, auth, file, or schema surface was added.

## User Setup Required

None — verification is entirely local and used fixture providers, fake leases, and local child processes. No device, SSH, network, deployment, or hardware test was contacted.

## Next Phase Readiness

Runtime composition can select a host mode from controlled configuration and expose contamination/restart-required status without weakening the existing process-isolation default.

## Self-Check: PASSED

- All created implementation, public API, and test files exist in the worktree.
- RED/GREEN/fix commits `b007de8`, `60f9851`, `5620c20`, `b805d87`, and `637b0b7` exist in git history.
- No stubs, skipped tests, or unrun verification commands remain.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
