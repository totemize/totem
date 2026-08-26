---
phase: HW-01-capability-oriented-hardware-runtime
plan: "07"
subsystem: hardware-runtime
tags: [python, resource-broker, leases, concurrency, normalization, security]
requires:
  - phase: HW-01-06
    provides: Complete deterministic BindingRecord claim sets before host startup
provides:
  - Atomic normalized single- and multi-binding resource acquisition
  - Generation- and token-bound resource leases with confirmed-owner release
  - Deterministic conflict diagnostics and credential-redacted snapshots
affects: [runtime-lifecycle, process-host, in-process-host, radio-resources]
tech-stack:
  added: []
  patterns: [locked all-or-none lease transaction, normalized resource keys, explicit nonexclusive coexistence, redacted diagnostics]
key-files:
  created: [tests/unit/hardware_runtime/test_broker.py]
  modified: [src/totem/hardware/runtime/broker.py]
key-decisions:
  - "Resource identity is normalized by resource family, preserving case-sensitive path and D-Bus identifiers while redacting credential identifiers."
  - "A release requires the active binding ID, generation, and constant-time checked owner token; snapshots omit tokens and credential values."
patterns-established:
  - "Validate every requested resource and all release ownership before mutating broker tables."
  - "Nonexclusive claims may coexist only when every current and requested claimant is nonexclusive; compatibility groups remain immutable lease data."
requirements-completed: [RUN-02]
coverage:
  - id: D1
    description: Atomic normalized resource acquisition produces one complete concurrent winner, deterministic conflict evidence, and no partial lease.
    requirement: RUN-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_broker.py
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime -x
        status: pass
    human_judgment: false
  - id: D2
    description: Exact generation-owner release, nonexclusive sharing, compatibility-group data, and credential-redacted diagnostic snapshots.
    requirement: RUN-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_broker.py
        status: pass
    human_judgment: false
metrics:
  duration: 7m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 07: Atomic Resource Brokerage Summary

**A generic, provider-free broker now atomically leases normalized resource claim sets, permits only explicit nonexclusive sharing, and ties release to an exact binding generation and owner token.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-26T11:33:00Z
- **Completed:** 2026-08-26T11:40:25Z
- **Tasks:** 1/1
- **Files modified:** 2

## Accomplishments

- Added deterministic `ResourceKey`, `ResourceLease`, and `ResourceConflict` contracts for GPIO, SPI, I2C, block, path, PHY, interface, adapter, D-Bus, socket, credential, and compatibility claims.
- Added locked `acquire_many` validation/commit so a complete binding-plan segment gains every resource or none, with the normalized key plus existing/requesting owners on conflict.
- Added explicit nonexclusive coexistence, immutable compatibility-group lease data, generation counters, token-authorized release, and ordered snapshots that redact credentials and owner tokens.
- Added fixture-only concurrent, rollback, release-token, compatibility, duplicate-normalization, and redaction proofs.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_broker.py -x` — passed (7 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (79 tests).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (215 tests).
- `.venv/bin/python -m compileall -q src/totem/hardware/runtime` — passed.
- `git diff --check` — passed.
- Source audit confirmed `broker.py` has no concrete-provider, legacy-manager, fixture-provider, or dynamic-import dependency.

## TDD Gate Compliance

- RED `f7163ef` added the failing broker contract and failed because the planned resource API was absent.
- GREEN `ecacb27` implemented atomic normalized leases; focused, hardware-runtime, and full local unit suites pass.

## Task Commits

1. **Task 1 RED: Specify atomic resource leases** — `f7163ef` (`test`)
2. **Task 1 GREEN: Atomically broker resource leases** — `ecacb27` (`feat`)

## Files Created/Modified

- `src/totem/hardware/runtime/broker.py` — generic transactional resource broker, normalized keys, lease ownership, conflicts, and safe snapshots.
- `tests/unit/hardware_runtime/test_broker.py` — fixture-only concurrent acquisition, rollback, sharing, release, and redaction coverage.

## Decisions Made

- Normalization casefolds device naming families while preserving case-sensitive path and D-Bus identities; credential identities remain comparable internally but always render as `<redacted>`.
- `release` is intentionally a confirmed-owner operation: the supervisor must provide the active binding ID, generation, and owner token, preventing stale or substituted hosts from freeing a replacement lease.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Compatibility] Retained the existing lease binding accessor**
- **Found during:** Task 1 full hardware-runtime verification
- **Issue:** The established catalog-to-claim tracer reads `claim.binding`; replacing the old record shape with a lease removed that accessor.
- **Fix:** Stored the originating `BindingRecord` on each live `ResourceLease` while preserving the provider-free broker boundary.
- **Files modified:** `src/totem/hardware/runtime/broker.py`
- **Verification:** `tests/unit/hardware_runtime/test_catalog_claim_tracer.py` passes within the 79-test hardware-runtime suite.
- **Committed in:** `ecacb27`

**2. [Rule 2 - Transaction safety] Validate every release owner before deleting any resource entry**
- **Found during:** Task 1 release-path review
- **Issue:** An inconsistent internal owner table could otherwise delete an earlier resource before discovering a later ownership mismatch.
- **Fix:** Added a complete prevalidation pass before release-table mutation.
- **Files modified:** `src/totem/hardware/runtime/broker.py`
- **Verification:** Focused broker release tests and the full local unit suite pass.
- **Committed in:** `ecacb27`

**Total deviations:** 2 auto-fixed (1 Rule 1 compatibility, 1 Rule 2 transaction safety). **Impact:** Both preserve compatibility and atomic release semantics without expanding architecture.

## Known Stubs

None. The empty owner token used only to construct an uncommitted diagnostic owner during pre-commit conflict validation cannot flow into a live lease or snapshot.

## Issues Encountered

- The RED path-normalization expectation initially treated `/var/lib/../run` as `/run`; it was corrected to the actual normalized `/var/run` path before GREEN verification.

## User Setup Required

None — all verification uses local fixtures and no external service or device setup.

## Next Phase Readiness

Lifecycle supervision can acquire complete binding claim sets before host initialization and only release a lease after confirming the matching generation. Radio-specific compatibility policy can consume the retained compatibility-group data in its dedicated plan.

## Self-Check: PASSED

- `src/totem/hardware/runtime/broker.py` and `tests/unit/hardware_runtime/test_broker.py` exist in the worktree.
- RED and GREEN commits `f7163ef` and `ecacb27` exist in git history.
- No plan-blocking stubs, skipped tests, or unrun verifications were found.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
