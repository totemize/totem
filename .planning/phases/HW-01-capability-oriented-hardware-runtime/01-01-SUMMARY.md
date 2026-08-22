---
phase: HW-01-capability-oriented-hardware-runtime
plan: "01"
subsystem: testing
tags: [python-3.9, pytest, dbus-next, deterministic-fixtures, ast-import-guard, no-contact]
requires: []
provides:
  - Controlled Python 3.9-compatible local test interpreter and dependency seam
  - Deterministic clock, process, socket, broker, and transcript fixtures
  - Canonical hardware ownership import guard and local-only benchmark shell
affects: [hardware-runtime, driver-hosts, protocol-conformance, benchmarks]
tech-stack:
  added: [tomli conditional dependency, dbus-next dev-test dependency]
  patterns: [controlled .venv commands, deterministic lifecycle fixtures, AST ownership enforcement]
key-files:
  created:
    - tests/unit/hardware_runtime/conftest.py
    - tests/unit/hardware_runtime/test_import_boundaries.py
    - tests/fixtures/hardware_runtime/protocol-vectors.json
    - tests/benchmarks/hardware_runtime/harness.py
  modified:
    - pyproject.toml
    - .planning/phases/HW-01-capability-oriented-hardware-runtime/01-VALIDATION.md
key-decisions:
  - "All later local Python claims use .venv/bin/python, currently Python 3.9.6."
  - "The benchmark shell emits local-synthetic-only evidence and cannot claim Pi acceptance."
patterns-established:
  - "Use FakeClock sleep to advance controlled time rather than block wall-clock tests."
  - "Use AST scans to prevent canonical hardware modules importing legacy owners."
requirements-completed: [TST-04]
coverage:
  - id: D1
    description: Controlled local interpreter plus deterministic lifecycle, socket, broker, and transcript seams
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit -x -q --tb=short
        status: pass
    human_judgment: false
  - id: D2
    description: Canonical hardware import guard, carrier-neutral vectors, and local-only benchmark harness
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py#test_import_guard_reports_forbidden_importing_file_and_module
        status: pass
      - kind: other
        ref: .venv/bin/python tests/benchmarks/hardware_runtime/harness.py --iterations 3
        status: pass
    human_judgment: false
duration: 17min
completed: 2026-08-22
status: complete
---

# Phase HW-01 Plan 01: Capability-Oriented Hardware Runtime Foundation Summary

**Python 3.9-controlled deterministic test seams with canonical import ownership enforcement and a local-only benchmark harness**

## Performance

- **Duration:** 17 min
- **Started:** 2026-08-22T15:29:39Z
- **Completed:** 2026-08-22T15:46:34Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments

- Created the controlled `.venv/bin/python` environment under Python 3.9.6, declared `tomli` only for Python below 3.11, and declared `dbus-next` as a reproducible development/test dependency.
- Added deterministic fakes for time, supervised child lifecycle, fragmented streams, resource leases, and provider transcripts.
- Added AST-based import-boundary coverage, carrier-neutral protocol vectors, and a local synthetic benchmark shell that reports no hardware contact or Pi acceptance.
- Recorded quick-gate evidence and a passing 143-test controller-only full-suite result in the phase validation ledger.

## Task Commits

1. **Task 1: Create the controlled Python environment and Wave-0 fixtures** — `df13761` (test), `879f27f` (feat)
2. **Post-wave integration correction: portable driver-contract test dependency** — `2f192bc` (fix)

## Files Created/Modified

- `pyproject.toml` — declares Python <3.11 `tomli` compatibility and unmarked `dbus-next` development/test dependencies while retaining the Linux-only production marker.
- `tests/unit/hardware_runtime/conftest.py` — deterministic fakes and AST ownership scan.
- `tests/unit/hardware_runtime/test_import_boundaries.py` — focused Wave-0 fixture and import-boundary coverage.
- `tests/fixtures/hardware_runtime/protocol-vectors.json` — static JSON request/result/error/event vectors.
- `tests/benchmarks/hardware_runtime/harness.py` — non-contact synthetic workload entry point.
- `01-VALIDATION.md` — controlled interpreter, timings, no-contact evidence, and baseline result.

## Verification

- `test -x .venv/bin/python && .venv/bin/python -c 'import sys; assert sys.version_info >= (3, 9)' && .venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py -x` — passed (7 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (7 tests, under 1 s elapsed).
- `.venv/bin/python tests/benchmarks/hardware_runtime/harness.py --iterations 3` — passed; emitted `hardware_contacted: false` and `pi_acceptance: false`.
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (143 tests in 0.86 s).

## Decisions Made

- Later plans must use the newly established `.venv/bin/python` interpreter for every local Python and pytest claim.
- Synthetic controller evidence is explicitly labeled local-only; it cannot establish Pi-class acceptance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Declared the driver-contract test dependency for non-Linux controllers**
- **Found during:** Post-wave integration gate
- **Issue:** The full macOS unit suite imported the Linux-only NetworkManager Wi-Fi driver contract but did not install `dbus-next`, stopping after 23 passing tests.
- **Fix:** Added the existing constrained `dbus-next` release to Poetry's dev dependency group, leaving the Linux-only runtime dependency unchanged.
- **Files modified:** `pyproject.toml`, `01-VALIDATION.md`, `01-01-SUMMARY.md`
- **Verification:** `.venv/bin/python -m pytest tests/unit -x -q --tb=short` passed 143 tests in 0.86 s.
- **Committed in:** `2f192bc` (fix) and this metadata commit.

---

**Total deviations:** 1 auto-fixed (1 blocking test-environment correction).
**Impact on plan:** Restores reproducible full local coverage without changing production Linux dependency behavior or hardware scope.

## Issues Encountered

None — the post-wave controller portability failure was resolved by a declared test dependency.

## Known Stubs

None.

## Next Phase Readiness

Wave-0 provides the controlled test foundation for public API, catalog, resolver, host, and benchmark plans, with the current full unit suite passing locally. Pi-class performance and deployment acceptance remain explicitly deferred until hardware allocation.

## Self-Check: PASSED

- Created fixtures, vectors, benchmark harness, and validation ledger exist in the worktree.
- TDD RED and GREEN commits `df13761` and `879f27f`, plus portability correction `2f192bc`, exist in git history.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-22*
