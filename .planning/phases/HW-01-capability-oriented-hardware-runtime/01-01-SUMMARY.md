---
phase: HW-01-capability-oriented-hardware-runtime
plan: "01"
subsystem: testing
tags: [python-3.9, pytest, deterministic-fixtures, ast-import-guard, no-contact]
requires: []
provides:
  - Controlled Python 3.9-compatible local test interpreter and dependency seam
  - Deterministic clock, process, socket, broker, and transcript fixtures
  - Canonical hardware ownership import guard and local-only benchmark shell
affects: [hardware-runtime, driver-hosts, protocol-conformance, benchmarks]
tech-stack:
  added: [tomli conditional dependency]
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
duration: 4min
completed: 2026-08-22
status: complete
---

# Phase HW-01 Plan 01: Capability-Oriented Hardware Runtime Foundation Summary

**Python 3.9-controlled deterministic test seams with canonical import ownership enforcement and a local-only benchmark harness**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-22T15:29:39Z
- **Completed:** 2026-08-22T15:33:34Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments

- Created the controlled `.venv/bin/python` environment under Python 3.9.6 and declared `tomli` only for Python below 3.11.
- Added deterministic fakes for time, supervised child lifecycle, fragmented streams, resource leases, and provider transcripts.
- Added AST-based import-boundary coverage, carrier-neutral protocol vectors, and a local synthetic benchmark shell that reports no hardware contact or Pi acceptance.
- Recorded quick-gate evidence and the existing controller-only full-suite failure in the phase validation ledger.

## Task Commits

1. **Task 1: Create the controlled Python environment and Wave-0 fixtures** — `df13761` (test), `879f27f` (feat)

## Files Created/Modified

- `pyproject.toml` — declares the Python <3.11 `tomli` compatibility dependency.
- `tests/unit/hardware_runtime/conftest.py` — deterministic fakes and AST ownership scan.
- `tests/unit/hardware_runtime/test_import_boundaries.py` — focused Wave-0 fixture and import-boundary coverage.
- `tests/fixtures/hardware_runtime/protocol-vectors.json` — static JSON request/result/error/event vectors.
- `tests/benchmarks/hardware_runtime/harness.py` — non-contact synthetic workload entry point.
- `01-VALIDATION.md` — controlled interpreter, timings, no-contact evidence, and baseline result.

## Verification

- `test -x .venv/bin/python && .venv/bin/python -c 'import sys; assert sys.version_info >= (3, 9)' && .venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py -x` — passed (7 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (7 tests, under 1 s elapsed).
- `.venv/bin/python tests/benchmarks/hardware_runtime/harness.py --iterations 3` — passed; emitted `hardware_contacted: false` and `pi_acceptance: false`.
- `.venv/bin/python -m pytest tests/unit -x` — baseline recorded: 23 passed, then an existing macOS `dbus_next` import failure from a Linux-only Wi-Fi dependency.

## Decisions Made

- Later plans must use the newly established `.venv/bin/python` interpreter for every local Python and pytest claim.
- Synthetic controller evidence is explicitly labeled local-only; it cannot establish Pi-class acceptance.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The full current unit baseline stops at `tests/unit/test_driver_contracts.py` because the existing `pyproject.toml` declares `dbus-next` only for Linux while the local macOS controller imports a NetworkManager Wi-Fi driver. This pre-existing platform baseline is recorded in `01-VALIDATION.md`; the focused Wave-0 gate passes.

## Known Stubs

None.

## Next Phase Readiness

Wave-0 provides the controlled test foundation for public API, catalog, resolver, host, and benchmark plans. Pi-class performance and deployment acceptance remain explicitly deferred until hardware allocation.

## Self-Check: PASSED

- Created fixtures, vectors, benchmark harness, and validation ledger exist in the worktree.
- TDD RED and GREEN commits `df13761` and `879f27f` exist in git history.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-22*
