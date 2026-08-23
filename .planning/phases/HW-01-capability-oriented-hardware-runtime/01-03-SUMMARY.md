---
phase: HW-01-capability-oriented-hardware-runtime
plan: "03"
subsystem: hardware-runtime
tags: [python, plugin-catalog, discovery, resource-broker, import-boundary]
requires:
  - phase: HW-01-02
    provides: Public immutable driver contracts and fixture provider package data
provides:
  - Import-free immutable catalog snapshots from installed distribution metadata
  - Exact-facts capability resolution into generic binding records
  - Normalized atomic resource claims with generation-stamped ownership
affects: [driver-hosts, lifecycle, configuration, capability-runtime]
tech-stack:
  added: []
  patterns: [package-data manifest validation, startup-bound catalog snapshots, exact resource facts, atomic claims]
key-files:
  created:
    - src/totem/hardware/catalog/metadata.py
    - src/totem/hardware/catalog/manifests.py
    - src/totem/hardware/discovery/facts.py
    - src/totem/hardware/discovery/resolver.py
    - src/totem/hardware/runtime/bindings.py
    - src/totem/hardware/runtime/broker.py
    - tests/unit/hardware_runtime/test_catalog_claim_tracer.py
  modified: []
key-decisions:
  - "The catalog captures one locked, immutable metadata snapshot per controlled runtime start."
  - "The resolver matches provider resource declarations only against exact observed facts before issuing a generic binding."
  - "The broker normalizes every resource identity and atomically grants all of a binding's claims or none."
requirements-completed: [HWR-03, SPI-01]
duration: 4min
completed: 2026-08-23
status: complete
---

# Phase HW-01 Plan 03: Catalog Claim Tracer Summary

**An installed fixture distribution now traverses package-data cataloging, exact fact resolution, and a generation-stamped SPI claim without importing its provider.**

## Accomplishments

- Added an import-free `CatalogScanner` that reads only entry-point metadata and exact package-data manifests, rejects incompatible API majors with safe diagnostics, deduplicates records, and freezes one ordered startup snapshot.
- Added immutable `HardwareFacts`, deterministic `Resolver`, and `BindingRecord` values that choose a single generic capability binding or return structured unavailable/ambiguous evidence.
- Added `ResourceBroker`, which normalizes claims and performs all-or-nothing exclusive ownership under a lock before any future provider host can run.
- Proved the installed fixture, empty, incompatible, ambiguous, conflicting, adjacent-startup, repeated, and concurrent paths while retaining the provider import sentinel unset.

## Verification

- `./.venv/bin/python -m compileall -q src/totem/hardware tests/unit/hardware_runtime/test_catalog_claim_tracer.py` — passed.
- `./.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py tests/unit/hardware_runtime/test_import_boundaries.py -x -q --tb=short` — passed (13 tests).
- `./.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (152 tests).

## Task Commits

1. **Task 1 RED: Trace an installed fixture to one atomically claimed binding** — `7136db7` (`test`)
2. **Task 1 GREEN: Trace an installed fixture to one atomically claimed binding** — `f19d31a` (`feat`)

## Decisions Made

- Distribution metadata changes are intentionally observed only by a newly created scanner, so a running daemon retains one immutable startup plan.
- Resource availability is an exact fact (`resource.<kind> = identifier`) at this tracer stage; profile/ranking rules remain a later resolver expansion.
- The broker rejects any duplicate normalized claim now, failing closed before provider execution and leaving no partial ownership.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Next Phase Readiness

Plan 04 can consume the `BindingRecord` and `ClaimRecord` inputs to add provider-host execution while retaining the catalog-to-claim import boundary. Hardware acceptance remains deferred; no hardware-marked tests or device access occurred.

## Self-Check: PASSED

- All catalog, facts, resolver, binding, broker, and tracer test files exist in the worktree.
- RED and GREEN commits `7136db7` and `f19d31a` exist in git history.
