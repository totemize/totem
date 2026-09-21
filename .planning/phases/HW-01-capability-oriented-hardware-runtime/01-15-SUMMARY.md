---
phase: HW-01-capability-oriented-hardware-runtime
plan: "15"
subsystem: hardware-display-compatibility
tags: [waveshare, eink, compatibility-facade, ast, import-boundary, pytest]
requires:
  - phase: HW-01-13
    provides: Provider-owned auxiliary mock, 3.7, Pi 5, and vendored 3.7 support.
provides:
  - Six exact historical mock, Waveshare 3.7, and vendor-support compatibility re-exports.
  - An exhaustive AST/inventory guard against reintroducing legacy auxiliary display ownership.
affects: [HW-01-28, legacy-contracts, registry-facade]
tech-stack:
  added: []
  patterns:
    - Import-safe legacy facades use direct canonical re-exports with exact package inventories.
    - Hardware-active vendored support is verified by source identity rather than local import.
key-files:
  created:
    - tests/unit/test_display_aux_compat.py
  modified:
    - src/totem/devices/display/drivers/mock_eink.py
    - src/totem/devices/display/drivers/waveshare_3in7.py
    - src/totem/devices/display/drivers/waveshare_3in7_pi5.py
    - src/totem/devices/display/waveshare_epd/__init__.py
    - src/totem/devices/display/waveshare_epd/epd3in7.py
    - src/totem/devices/display/waveshare_epd/epdconfig.py
key-decisions:
  - "Legacy auxiliary paths preserve canonical objects directly; wrappers, fallbacks, and legacy ownership are prohibited."
  - "Vendor support whose canonical import selects a platform is proven by exact source re-export audit, never by a local hardware-active import."
patterns-established:
  - "A complete compatibility table must enumerate every legacy module and its canonical target before a facade is accepted."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Every historical auxiliary display path is an exact canonical re-export without legacy provider or I/O ownership.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_display_aux_compat.py
        status: pass
    human_judgment: false
  - id: D2
    description: Auxiliary legacy modules contain only canonical imports, explicit exports, and documentation.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_display_aux_compat.py and tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
  - id: D3
    description: Compatibility retains local-only coverage while avoiding active vendor platform imports.
    requirement: TST-04
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/test_display_aux_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
duration: 4min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 15: Auxiliary Display Compatibility Facades Summary

**Six historical mock, Waveshare 3.7, Pi 5, and vendor-support paths now resolve only through canonical provider-owned modules, guarded by exhaustive identity, inventory, and AST tests.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-26T12:50:13Z
- **Completed:** 2026-08-26T12:54:00Z
- **Tasks:** 1/1
- **Files modified:** 7

## Accomplishments

- Replaced all six auxiliary legacy modules with canonical re-exports, removing environment probing, mock fallback, vendor I/O, resource-selection, and platform ownership from `totem.devices`.
- Added a complete six-path table covering mock, 3.7, Pi 5, package, EPD, and platform-support paths; safe driver imports prove exact object/signature identity.
- AST/source audits prove every legacy module contains only documentation, canonical imports, and explicit exports; hardware-active vendor support is examined without importing it.

## Task Commits

1. **Task 1: Replace auxiliary display paths with re-exports (RED)** — `9976b8a` (`test`)
2. **Task 1: Replace auxiliary display paths with re-exports (GREEN)** — `bd168d0` (`feat`)

## Files Created/Modified

- `tests/unit/test_display_aux_compat.py` — Exact six-path inventory plus identity/signature and AST source-boundary proof.
- `src/totem/devices/display/drivers/mock_eink.py` — Canonical mock transport re-export.
- `src/totem/devices/display/drivers/waveshare_3in7.py` — Canonical 3.7 driver re-export.
- `src/totem/devices/display/drivers/waveshare_3in7_pi5.py` — Canonical Pi 5 3.7 driver re-export.
- `src/totem/devices/display/waveshare_epd/` — Canonical vendor package, EPD, and platform-support re-exports.

## Verification

- `.venv/bin/python -m pytest tests/unit/test_display_aux_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 17 passed.
- SEC-01 import/manifest subset — 3 passed; available SEC-09 resolver/lifecycle evidence subset — 4 passed.
- AST source audit, `compileall`, and `git diff --check` — passed.
- `tests/unit/test_driver_contracts.py -k 'mock or waveshare_3in7'` — 4 expected stale legacy-contract failures recorded in migration window 10 for Plan 01-28; the out-of-scope test was not changed.

## Decisions Made

- Retain exact canonical class/function identity at import-safe legacy paths rather than wrapping or subclassing provider classes.
- Source-audit vendor re-exports instead of importing the canonical vendor module because its platform selector is intentionally hardware-active at import time.
- Keep stale `DeviceDriver` inheritance and `mock_eink.Driver.health()` expectations as the existing Plan 01-28 migration window rather than violating API-05 clean-break ownership.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Avoided a hardware-active vendor import during compatibility verification**
- **Found during:** Task 1 (Replace auxiliary display paths with re-exports)
- **Issue:** Importing canonical `waveshare_epd.epd3in7` loads its platform selector and fails locally while searching for the platform SPI shared object, violating the local-only no-hardware constraint.
- **Fix:** Limited runtime identity/signature checks to import-safe driver facades and proved vendor compatibility through exact canonical import targets plus AST/source inventory.
- **Files modified:** `tests/unit/test_display_aux_compat.py`
- **Verification:** Compatibility, import-boundary, compile, and source audits pass without importing the hardware-active vendor support.
- **Committed in:** `bd168d0` (part of Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking issue).
**Impact on plan:** Preserved the required canonical re-export and import-boundary architecture without device or platform-library contact.

## Issues Encountered

- Migration window 10 now records 17 stale legacy display-contract assertions for Plan 01-28: the prior 13 Waveshare 2.13 assertions plus three auxiliary `DeviceDriver` inheritance assertions and the removed mock-driver `health()` expectation.
- The future SEC-09 final-regression test file is not present yet. Its unrun verification is recorded as Windows ledger entry 11; available SEC-09 resolver/lifecycle checks passed.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Later facade migration can rely on one canonical owner for all auxiliary display paths.
- Plan 01-28 owns conversion/removal of the stale legacy `test_driver_contracts.py` assertions.
- No device, SSH, network, deployment, GPIO/SPI/display initialization, hardware-marked test, or physical resource was contacted.

## Self-Check: PASSED

- The compatibility test, all six legacy facade modules, Windows ledger updates, and this summary exist.
- TDD commits `9976b8a` and `bd168d0` exist on `refactor/hardware-ontology`.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
