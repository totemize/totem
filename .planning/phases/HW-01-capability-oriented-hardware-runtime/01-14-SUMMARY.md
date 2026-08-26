---
phase: HW-01-capability-oriented-hardware-runtime
plan: "14"
subsystem: hardware-display-compatibility
tags: [waveshare, eink, compatibility-facade, ast, pytest]
requires:
  - phase: HW-01-12
    provides: Provider-owned Waveshare 2.13 implementations with injected transports.
provides:
  - Eight exact legacy-to-canonical Waveshare 2.13 identity re-exports.
  - AST-gated compatibility inventory that rejects legacy implementation bodies.
affects: [HW-01-28, legacy-contracts, registry-facade]
tech-stack:
  added: []
  patterns:
    - Legacy hardware facades import one canonical provider symbol and expose no ownership logic.
    - Compatibility inventories derive exact package membership and check identity plus constructor signatures.
key-files:
  created:
    - tests/unit/test_display_2in13_compat.py
  modified:
    - src/totem/devices/display/drivers/_waveshare_2in13_base.py
    - src/totem/devices/display/drivers/waveshare_2in13.py
    - src/totem/devices/display/drivers/waveshare_2in13_pi5.py
    - src/totem/devices/display/drivers/waveshare_2in13_pi5_sw_cs.py
    - src/totem/devices/display/drivers/waveshare_2in13_v1.py
    - src/totem/devices/display/drivers/waveshare_2in13_v2.py
    - src/totem/devices/display/drivers/waveshare_2in13_v3.py
    - src/totem/devices/display/drivers/waveshare_2in13_v4.py
key-decisions:
  - "Legacy 2.13 facades preserve canonical class identity rather than wrapping or subclassing provider classes."
  - "The obsolete DeviceDriver inheritance assertions stay as a dependency-ordered migration window for Plan 01-28, because satisfying them now would violate API-05 clean-break ownership."
patterns-established:
  - "A legacy facade must be a canonical import plus __all__, and its exact path inventory must be AST-verified."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Every historical Waveshare 2.13 class path resolves to the exact canonical provider class with the same constructor signature.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_display_2in13_compat.py#test_legacy_imports_reexport_the_canonical_class_with_its_signature
        status: pass
    human_judgment: false
  - id: D2
    description: Legacy 2.13 modules contain only canonical imports, exports, and documentation, with an exact path inventory.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_display_2in13_compat.py#test_legacy_modules_contain_only_canonical_reexports
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
  - id: D3
    description: Compatibility imports remain exhaustive and local-only for every 2.13 variant.
    requirement: TST-04
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/test_display_2in13_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
duration: 5min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 14: Waveshare 2.13 Compatibility Facades Summary

**All eight historical Waveshare 2.13 module paths now re-export the exact provider-owned classes, with AST and signature gates preventing legacy hardware ownership from returning.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-08-26T12:42:47Z
- **Completed:** 2026-08-26T12:48:13Z
- **Tasks:** 1/1
- **Files modified:** 10

## Accomplishments

- Replaced the historical common base plus generic, Pi 5, and V1-V4 2.13 modules with canonical provider re-exports.
- Added an exact eight-row legacy/canonical inventory that verifies module membership, class identity, constructor signatures, and re-export-only AST bodies.
- Confirmed source contains no legacy I/O, probing, resource claims, provider selection, fallback loading, or lifecycle implementation.

## Task Commits

1. **Task 1: Replace the complete legacy 2.13 family (RED)** — `c82c12d` (`test`)
2. **Task 1: Replace the complete legacy 2.13 family (GREEN)** — `64e88c0` (`feat`)

## Files Created/Modified

- `tests/unit/test_display_2in13_compat.py` — Exact inventory, canonical identity/signature, and AST facade proof.
- `src/totem/devices/display/drivers/_waveshare_2in13_base.py` — Canonical base-class re-export.
- `src/totem/devices/display/drivers/waveshare_2in13*.py` — Seven provider class re-exports without legacy implementation bodies.
- `src/totem/devices/display/drivers/__init__.py` — Documents the legacy compatibility namespace.

## Verification

- `.venv/bin/python -m pytest tests/unit/test_display_2in13_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 24 passed.
- `.venv/bin/python -m compileall -q src/totem/devices/display/drivers` and `git diff --check HEAD~1 HEAD` — passed.
- Direct eight-row identity/signature and AST/import inventory audit — passed.
- Source audit for implementation declarations, `spidev`, `gpiod`, `gpiozero`, `RPi.GPIO`, direct open, environment probing, claims, lifecycle, and selection in all legacy 2.13 modules — passed with no matches.

## Decisions Made

- Preserve the exact canonical class object at legacy paths; wrappers or legacy subclassing would undermine the new provider ownership boundary.
- Retain the stale legacy `DeviceDriver` contract checks as a planned migration window owned by Plan 01-28 rather than restoring prohibited legacy base ownership.

## Deviations from Plan

None - plan implementation and required verification executed exactly as written.

## Issues Encountered

- `.venv/bin/python -m pytest tests/unit/test_driver_contracts.py -k waveshare` reports 13 stale legacy-contract failures: seven require `DeviceDriver` inheritance and six monkeypatch removed legacy-base internals. This is a temporary dependency-ordered window owned by Plan 01-28 (legacy contracts/registry facade). Satisfying it in this plan would violate the required API-05 clean break by adding an ownership wrapper or making canonical providers inherit a legacy contract.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-28 can retire or translate the obsolete legacy contract/registry assertions after its facade migration work.
- No device, SSH, deployment, network, GPIO/SPI/display initialization, or hardware-marked test was contacted.

## Self-Check: PASSED

- The compatibility test, all eight legacy facade modules, and this summary exist.
- TDD commits `c82c12d` and `64e88c0` exist on `refactor/hardware-ontology`.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
