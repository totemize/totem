---
phase: HW-01-capability-oriented-hardware-runtime
plan: "13"
subsystem: hardware-display
tags: [waveshare, eink, vendor-support, mock-transport, pytest]
requires:
  - phase: HW-01-11
    provides: Import-free built-in display manifest and child-only provider boundary.
  - phase: HW-01-12
    provides: Exhaustive provider-package inventory pattern for migrated display variants.
provides:
  - Provider-owned mock, Waveshare 3.7, Pi 5, and vendored 3.7 support modules.
  - Exact auxiliary family inventory, explicit mock behavior, and catalog import-boundary coverage.
affects: [HW-01-14, display-migration, compatibility-facades]
tech-stack:
  added: []
  patterns:
    - Catalog tests enumerate vendor support by source path so they never execute a hardware-active vendor adapter.
    - Auxiliary display modules remain child-owned; mock selection is explicit and absent from the production manifest.
key-files:
  created:
    - src/totem/hardware/builtin/display/drivers/mock_eink.py
    - src/totem/hardware/builtin/display/drivers/waveshare_3in7.py
    - src/totem/hardware/builtin/display/drivers/waveshare_3in7_pi5.py
    - src/totem/hardware/builtin/display/waveshare_epd/epd3in7.py
    - src/totem/hardware/builtin/display/waveshare_epd/epdconfig.py
  modified:
    - tests/unit/hardware_runtime/test_builtin_display_aux_variants.py
key-decisions:
  - "Keep vendored 3.7 support inside the provider child package and inspect it by path during catalog tests rather than importing it."
  - "Keep mock_eink as an explicit test transport only; it is not a production manifest variant or unsupported-hardware fallback."
patterns-established:
  - "Exhaustive auxiliary display tests must assert both driver module membership and every vendored Python support file."
requirements-completed: [HWR-02, TST-04]
coverage:
  - id: D1
    description: Provider-owned mock and Waveshare 3.7/Pi 5 implementations plus vendored 3.7 support.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_aux_variants.py
        status: pass
    human_judgment: false
  - id: D2
    description: Exact auxiliary inventory, explicit mock semantics, and catalog/provider import boundaries.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_aux_variants.py tests/unit/test_mock_transports.py tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 13: Auxiliary Display Variant Migration Summary

**The mock and Waveshare 3.7 display family, including Pi 5 and vendored controller support, now lives under the canonical built-in provider with exhaustive mock-only ownership and import-boundary checks.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-26T12:26:51Z
- **Completed:** 2026-08-26T12:38:42Z
- **Tasks:** 1/1
- **Files modified:** 7

## Accomplishments

- Relocated the in-memory mock driver, Waveshare 3.7 wrapper, Pi 5 wrapper, and vendor support package into `totem.hardware.builtin.display` without retaining legacy-owner imports.
- Added an exact auxiliary inventory for three driver modules and all three vendored Python files, plus explicit in-memory mock semantics.
- Proved manifest cataloging does not import the provider or the vendor support package; mock selection remains absent from the production provider manifest.

## Task Commits

1. **Task 1: Migrate mock, 3.7, and vendor-support variants (RED)** — `20e7576` (`test`)
2. **Task 1: Migrate mock, 3.7, and vendor-support variants (GREEN)** — `660125b` (`feat`)
3. **Task 1: Normalize migrated vendor formatting** — `bcba159` (`style`)
4. **Task 1: Remove migrated vendor EOF whitespace** — `d3b6059` (`style`)

## Files Created/Modified

- `src/totem/hardware/builtin/display/drivers/mock_eink.py` — Explicit in-memory display transport.
- `src/totem/hardware/builtin/display/drivers/waveshare_3in7.py` — Canonical 3.7 wrapper that imports its provider-owned vendor support.
- `src/totem/hardware/builtin/display/drivers/waveshare_3in7_pi5.py` — Canonical Pi 5 3.7 mock/fallback-capable wrapper.
- `src/totem/hardware/builtin/display/waveshare_epd/` — Relocated Waveshare 3.7 vendor package.
- `tests/unit/hardware_runtime/test_builtin_display_aux_variants.py` — Exhaustive inventory, mock behavior, and import-boundary tests.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_aux_variants.py tests/unit/test_mock_transports.py -x` — 17 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_aux_variants.py tests/unit/test_mock_transports.py tests/unit/hardware_runtime/test_builtin_display_core.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 30 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_aux_variants.py tests/unit/hardware_runtime/test_builtin_display_core.py tests/unit/hardware_runtime/test_import_boundaries.py tests/unit/hardware_runtime/test_catalog_claim_tracer.py tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_broker.py -x` — 41 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -q -x` — 126 passed.
- `.venv/bin/python -m compileall -q src/totem/hardware/builtin/display` and `git diff --check` — passed.

## Decisions Made

- Vendor support remains child-only. Catalog and resolution inspect only manifest package data, never the provider or vendored controller modules.
- The mock driver remains an explicit test binding transport, never a fallback production variant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Avoided importing hardware-active vendor support during inventory coverage**

- **Found during:** Task 1: Migrate mock, 3.7, and vendor-support variants.
- **Issue:** Importing `waveshare_epd` merely to enumerate it executes `epdconfig`, whose legacy adapter selects a platform backend at import time.
- **Fix:** Enumerated vendored support by its source directory and added a `CatalogScanner` assertion that manifest inspection leaves the provider and vendor modules unloaded.
- **Files modified:** `tests/unit/hardware_runtime/test_builtin_display_aux_variants.py`.
- **Verification:** Focused, import-boundary, security-focused catalog/process/broker, and complete hardware-runtime suites passed.
- **Committed in:** `660125b`.

**Total deviations:** 1 auto-fixed (Rule 1 bug).

**Impact on plan:** The correction enforces the planned child-only import boundary without changing display behavior or expanding scope.

## Known Stubs

None.

## Issues Encountered

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The full display family now has provider-owned migration coverage through 2.13 and auxiliary variants.
- No device, SSH, deployment, network, GPIO/SPI, display initialization, or hardware-marked test was contacted.

## Self-Check: PASSED

- All migrated provider modules, vendor support files, exhaustive test, and summary exist.
- Task commits `20e7576`, `660125b`, `bcba159`, and `d3b6059` exist on `refactor/hardware-ontology`.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
