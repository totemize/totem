---
phase: HW-01-capability-oriented-hardware-runtime
plan: "04"
subsystem: hardware-runtime
tags: [python, fastapi, unix-socket, process-isolation, display, nip-5d]
requires:
  - phase: HW-01-03
    provides: Claimed generation-stamped fixture binding with atomic resource ownership
provides:
  - Default selected-child process host with session-bound readiness
  - Binding-backed display handle and generic capability dispatch table
  - Correlated bounded display-frame results through loopback POST /bus
affects: [driver-hosts, protocol, lifecycle, application-api]
tech-stack:
  added: []
  patterns: [framed JSON with raw attachments, session-bound child identity, generic binding dispatch]
key-files:
  created:
    - src/totem/hardware/hosts/protocol.py
    - src/totem/hardware/hosts/process.py
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/capabilities/display.py
    - src/totem/hardware/api/bus.py
    - src/totem/hardware/api/app.py
    - tests/unit/hardware_runtime/test_runtime_tracer.py
  modified: []
decisions:
  - "The parent owns provider and binding identity, verifies the child host.ready and each result against a per-spawn session, and never trusts payload identity."
  - "The process carrier and POST /bus share a bounded JSON envelope with explicit raw attachment descriptors; no provider-specific router or factory is introduced."
metrics:
  duration: 4m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 04: Process Host Bus Tracer Summary

**A claimed fixture binding now starts in an isolated child, publishes a generic display handle after `host.ready`, and returns a same-ID NIP-5D-shaped bus result with bounded raw frame data.**

## Accomplishments

- Added a minimal Unix socketpair carrier that frames canonical JSON headers with explicit, checksummed, bounded raw attachments.
- Added `ProcessDriverHost`, which starts the selected entry-point worker only after catalog resolution and broker claim, waits for a session-bound `host.ready`, and serializes concurrent exchanges over the one child connection.
- Added a selected-child worker that imports the fixture provider only inside the child and reports safe, correlated `.result` envelopes.
- Added a binding-backed `DisplayHandle`, a generic `HardwareBus` binding table, and a loopback ASGI `POST /bus` tracer using the same logical envelope.
- Proved that concurrent requests use the binding map rather than a driver-family router/factory, while unknown requests receive a stable public error with no traceback.

## Verification

- `./.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime_tracer.py -x` — passed (2 tests).
- `./.venv/bin/python -m compileall -q src/totem/hardware tests/unit/hardware_runtime/test_runtime_tracer.py` — passed.
- `./.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime_tracer.py tests/unit/hardware_runtime/test_catalog_claim_tracer.py tests/unit/hardware_runtime/test_import_boundaries.py -x -q --tb=short` — passed (15 tests).
- `./.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (154 tests).
- Scoped Flake8 could not run because it is not installed in `.venv`; this is not a plan verification command and all required compile/test checks passed.

## TDD Gate Compliance

- RED `aaabca5` failed at collection because the planned hardware API boundary did not exist.
- GREEN `a7dd575` added the process host, display handle, carrier, and bus path; the focused and full suites pass.

## Task Commits

1. **Task 1 RED: Specify the claimed-binding host and bus tracer** — `aaabca5` (`test`)
2. **Task 1 GREEN: Complete the process host and generic bus tracer** — `a7dd575` (`feat`)

## Decisions Made

- Parent-owned spawn sessions bind provider and binding identity across readiness and results, so the child payload cannot impersonate another binding.
- The tracer uses one logical NIP-5D-shaped envelope on the framed Unix carrier and application bus, while later protocol work can deepen the carrier without changing applications.
- A generic `binding_id -> DisplayHandle` table is sufficient for this slice; no per-driver registry, router, or factory was added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Restrict the child environment to selected runtime roots**
- **Found during:** Task 1
- **Issue:** Passing the parent process environment would give fixture-provider code undeclared ambient configuration.
- **Fix:** The worker receives only the temporary fixture site package, Totem source root, and `PYTHONNOUSERSITE`; it inherits no daemon environment or undeclared file descriptors.
- **Files modified:** `src/totem/hardware/hosts/process.py`
- **Verification:** Focused tracer/import-boundary suite passed (9 tests) and full unit suite passed (154 tests).
- **Commit:** `a7dd575`

**Total deviations:** 1 auto-fixed (Rule 2 security). **Impact:** Tightens the stated daemon-to-fixture trust boundary without changing the planned public tracer path.

## Known Stubs

None.

## Threat Flags

None — the framed Unix carrier and loopback bus endpoint are the planned trust surfaces, and this tracer applies bounded attachments, parent-bound identity, restricted child environment, and safe public errors.

## Next Phase Readiness

Plan 05 can add typed runtime configuration while preserving the claimed-binding → default child host → display handle → correlated bus path. Hardware acceptance remains deferred: no hardware-marked tests, device access, SSH, or deployment occurred.

## Self-Check: PASSED

- All host, capability, API, and tracer files listed above exist in the worktree.
- RED and GREEN commits `aaabca5` and `a7dd575` exist in git history.
