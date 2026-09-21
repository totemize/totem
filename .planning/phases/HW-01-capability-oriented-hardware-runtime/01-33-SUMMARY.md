---
phase: HW-01-capability-oriented-hardware-runtime
plan: "33"
subsystem: runtime validation and acceptance gate
tags: [python, pytest, hardware-runtime, benchmark, process-isolation, nip-5d, documentation]
requires:
  - phase: HW-01-08
    provides: Bounded THW1 canonical-JSON carrier and attachment contract.
  - phase: HW-01-09
    provides: Generation-aware process supervision and confirmed lease-release ordering.
  - phase: HW-01-10
    provides: Configurable in-process host and dual-host conformance behavior.
  - phase: HW-01-23
    provides: One eager runtime owner and opaque capability handles.
  - phase: HW-01-32
    provides: Single-runtime deployment command and systemd composition contracts.
provides:
  - Fail-closed, allocation-gated Pi benchmark evidence schema for provider and per-binding process grouping.
  - Public NIP-5D-shaped runtime, lifecycle, carrier, isolation, and compatibility contract documentation.
  - Phase-level local regression guard and final requirement-to-test validation ledger.
affects: [Pi acceptance, deployed-default cutover, hardware runtime maintenance]
tech-stack:
  added: []
  patterns:
    - A benchmark validator accepts explicit captured evidence only; it never discovers or contacts hardware.
    - Architecture acceptance requires complete provider and per-binding grouping records for each target architecture.
key-files:
  created:
    - scripts/benchmark_driver_host.py
    - tests/hardware/test_driver_host_bench.py
    - docs/hardware-driver-runtime.md
    - docs/hardware-driver-benchmark.md
    - tests/unit/test_phase1_regression.py
  modified:
    - tests/conftest.py
    - .planning/phases/HW-01-capability-oriented-hardware-runtime/01-VALIDATION.md
key-decisions:
  - "Pi evidence is captured by an explicitly allocated operator workflow and validated locally; the validator never discovers a target or starts a runtime."
  - "Canonical JSON and provider-default grouping remain provisional despite local green tests; only complete armv6l, armv7l, and aarch64 evidence can accept them."
patterns-established:
  - "Keep controller-safe schema tests beside opt-in hardware tests by checking explicit pytest markers rather than directory keywords."
requirements-completed: [HWR-04, ISO-01, TST-03, TST-04]
coverage:
  - id: D1
    description: Fail-closed benchmark workload and schema record process grouping, memory, latency, frame, event, recovery, cleanup, lease, and rollback evidence.
    requirement: TST-03
    verification:
      - kind: unit
        ref: tests/hardware/test_driver_host_bench.py
        status: pass
      - kind: other
        ref: .venv/bin/python scripts/benchmark_driver_host.py --self-test
        status: pass
    human_judgment: false
  - id: D2
    description: Public runtime and benchmark documentation preserve the NIP-5D-shaped boundary, sole ownership, configurable hosting, and manual cutover limitations.
    requirement: ISO-01
    verification:
      - kind: unit
        ref: tests/unit/test_phase1_regression.py#test_phase1_compatibility_inventory_and_public_contract_remain_present
        status: pass
    human_judgment: false
  - id: D3
    description: Final local architecture, compatibility, conformance, and cleanup contracts remain green under the controlled Python 3.9 environment.
    requirement: HWR-04
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit -x --tb=short
        status: pass
    human_judgment: false
  - id: D4
    description: Pi acceptance and deployed-default cutover are recorded as manual gates pending operator allocation and measured evidence on three architectures.
    requirement: ISO-01
    verification: []
    human_judgment: true
    rationale: Physical Pi PSS, fault recovery, lease, and rollback evidence cannot be produced without explicitly allocated hardware.
metrics:
  duration: "12m"
  completed: "2026-08-26"
status: complete
---

# Phase HW-01 Plan 33: Final Runtime Regression and Pi Acceptance Gate Summary

**A public capability-runtime contract, fail-closed Pi evidence validator, and 470-test local regression close the migration without claiming hardware or deployment acceptance.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-26T19:11:09+01:00
- **Completed:** 2026-08-26T19:19:39+01:00
- **Tasks:** 2/2
- **Files modified:** 8

## Accomplishments

- Added a pinned provider/per-binding benchmark workload that validates complete, credential-free armv6l, armv7l, and aarch64 evidence, including PSS-or-labeled-RSS, latency, 4,000-byte frame, event, recovery, lease, cleanup, and rollback fields.
- Published the public NIP-5D-shaped logical contract, THW1 carrier limits, process-default/in-process opt-in behavior, lifecycle/lease semantics, compatibility boundary, and manual Pi cutover procedure.
- Added a phase-level one-owner/import-boundary/compatibility regression guard; the final controlled local suite passed 470 tests in 32.15 seconds.
- Finalized the validation ledger as locally Nyquist-compliant while leaving Pi measurement and live-default cutover explicitly deferred.

## Task Commits

1. **Task 1 RED: Specify fail-closed Pi benchmark evidence** — `23ec54e` (`test`)
2. **Task 1 GREEN: Build the opt-in Pi benchmark workload and public acceptance runbook** — `3e1d461` (`feat`)
3. **Task 2 RED: Specify final local regression ledger** — `7c91d16` (`test`)
4. **Task 2 GREEN: Run full local conformance/regression and finalize the validation ledger** — `3a2bb0e` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/hardware/test_driver_host_bench.py --collect-only -q` — 5 collected; no hardware test execution.
- `.venv/bin/python scripts/benchmark_driver_host.py --self-test` — passed with `hardware_contacted: false` and `pi_acceptance: false`.
- `.venv/bin/python -m pytest tests/unit/test_phase1_regression.py -q` — 4 passed in 3.63 seconds.
- `.venv/bin/python -m pytest tests/unit -x --tb=short` — 470 passed in 32.15 seconds.
- `git diff --check` — passed.

All commands used `.venv/bin/python`, local fixtures, local child processes, source text, or static evidence records. No SSH, network, deployment, `systemctl`, live service, real device, USB, serial, I2C, GPIO, radio, or `--run-hardware` test execution occurred.

## Files Created/Modified

- `scripts/benchmark_driver_host.py` — Pinned workload, strict evidence schema, redaction checks, architecture matrix, and safe self-test CLI.
- `tests/hardware/test_driver_host_bench.py` — Controller-safe schema tests and one explicitly hardware-marked allocation path.
- `docs/hardware-driver-runtime.md` — Public runtime, carrier, ownership, hosting, lifecycle, and trust-boundary contract.
- `docs/hardware-driver-benchmark.md` — Pi measurement matrix plus manual cutover and rollback runbook.
- `tests/unit/test_phase1_regression.py` — Architecture, inventory, focused fixture, cleanup, and validation-ledger regression guard.
- `tests/conftest.py` — Correctly gates only explicitly marked hardware tests.
- `01-VALIDATION.md` — Final environment, timing, requirement/test mapping, and manual-gate ledger.

## Decisions Made

- Keep the benchmark validator non-operational: it validates pre-captured evidence and refuses incomplete or mislabeled architecture records rather than touching a target.
- Require both default provider grouping and explicit per-binding grouping evidence before an architecture can be accepted.
- Treat process isolation as fault containment, not package trust or OS sandboxing; systemd/device/D-Bus policy remains an operations security concern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test safety] Corrected the hardware marker gate for controller-safe benchmark schema tests**
- **Found during:** Task 1 GREEN.
- **Issue:** The collection hook treated the `tests/hardware/` directory keyword as an explicit hardware marker, skipping controller-safe schema tests.
- **Fix:** Gate only `item.iter_markers(name="hardware")`, keeping the true allocated-device test opt-in while running schema validation locally.
- **Files modified:** `tests/conftest.py`.
- **Verification:** 4 schema tests passed and the explicit hardware test remained skipped without `--run-hardware`.
- **Committed in:** `3e1d461`.

**2. [Rule 3 - Blocking reference] Replaced a removed legacy-facade test reference with the current compatibility inventory**
- **Found during:** Task 2 read-first checks.
- **Issue:** `tests/unit/test_legacy_facades.py` no longer exists; `tests/unit/test_api_facades.py` and the dedicated manager/device facade suites now own that coverage.
- **Fix:** The phase regression invokes and inventories the current facade contracts rather than recreating a stale file.
- **Files modified:** `tests/unit/test_phase1_regression.py`.
- **Verification:** Focused regression passed; full `tests/unit` suite passed 470 tests.
- **Committed in:** `3a2bb0e`.

**3. [Rule 2 - Project continuity] Recorded the required session journal entry and index**
- **Found during:** Plan close-out.
- **Issue:** `AGENTS.md` requires completed sessions in the dated journal and index.
- **Fix:** Recorded the Plan 01-33 local-only closure and its deferred hardware gates.
- **Files modified:** `.journey/journal/2026-08-26.md`, `.journey/README.md`.
- **Verification:** The dated entry and index row link the final local evidence to this plan.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 3 auto-fixed (Rule 1 test-safety, Rule 2 project continuity, Rule 3 blocking reference). **Impact:** The corrections preserve the no-contact boundary and current compatibility inventory; no hardware, deployment, or architectural scope expanded.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None for local validation.  Pi acceptance and deployed-default cutover require a separate, explicitly allocated operator run documented in `docs/hardware-driver-benchmark.md`.

## Next Phase Readiness

- Local migration evidence is complete and traceable; the capability-runtime contract is ready for review.
- Pi PSS/startup/latency/frame/event/recovery/lease/rollback evidence remains required for armv6l, armv7l, and aarch64.
- Do not change a deployed default until the complete six-row grouping matrix and a rollback-backed cutover exercise are accepted.

## TDD Gate Compliance

- RED commits `23ec54e` and `7c91d16` failed as expected before the benchmark contract and local-validation ledger existed.
- GREEN commits `3e1d461` and `3a2bb0e` passed their focused local checks; the final full local suite passed 470 tests.

## Self-Check: PASSED

- Found every declared script, test, documentation, validation, and summary file.
- Found task commits `23ec54e`, `3e1d461`, `7c91d16`, and `3a2bb0e` in repository history.
