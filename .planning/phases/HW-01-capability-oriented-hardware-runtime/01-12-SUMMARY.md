---
phase: HW-01-capability-oriented-hardware-runtime
plan: "12"
subsystem: hardware-display
tags: [waveshare, eink, display-provider, mock-transport, pytest]
requires:
  - phase: HW-01-11
    provides: Built-in display manifest, variant-neutral provider, and injected 2.13 transport/frame base.
provides:
  - Seven provider-owned Waveshare 2.13 variant module paths.
  - Exhaustive mock-only parameter coverage for variant inventory, frames, orientation, and Pi 5 chip-select behavior.
affects: [HW-01-13, display-migration, compatibility-facades]
tech-stack:
  added: []
  patterns:
    - Concrete display variants inherit the injected Waveshare 2.13 base and never probe hardware at import time.
    - The package inventory is mechanically compared with a single parameter table so untested variants fail.
key-files:
  created:
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_pi5.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_pi5_sw_cs.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v1.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v2.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v3.py
    - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v4.py
  modified:
    - tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py
key-decisions:
  - "Use the existing injected common base for every 2.13 panel, preserving each revision's controller command and framebuffer mapping."
  - "Represent Pi 5 hardware-CS and software-CS differences as explicit concrete transport kinds without device discovery or I/O at import time."
patterns-established:
  - "Variant inventories must assert exact package membership and test every row with mock transports."
requirements-completed: [HWR-02, TST-04]
coverage:
  - id: D1
    description: Seven provider-owned Waveshare 2.13 variants with preserved mock frame/orientation and Pi 5 transport semantics.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py
        status: pass
    human_judgment: false
  - id: D2
    description: Exact variant inventory and import-boundary proof for the display provider package.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py#test_provider_owns_an_exhaustive_2in13_variant_inventory
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
duration: 4min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 12: Waveshare 2.13 Variant Migration Summary

**All seven Waveshare 2.13 panel variants now live in the built-in display provider with import-safe injected transports and exhaustive mock-only behavioral coverage.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-26T12:18:59Z
- **Completed:** 2026-08-26T12:22:38Z
- **Tasks:** 1/1
- **Files modified:** 8

## Accomplishments

- Added canonical provider modules for generic, Pi 5 hardware-CS, Pi 5 software-CS, and V1–V4 2.13 panels.
- Preserved V1–V4 controller initialization, LUT, refresh, native framebuffer, and 180-degree mount behavior through the injected common base.
- Added one exhaustive package-derived parameter inventory that verifies every concrete path, import-time safety, frame mapping, and software-CS transfer wrapping.

## Task Commits

1. **Task 1: Migrate the complete 2.13 variant family (RED)** — `e4ce428` (`test`)
2. **Task 1: Migrate the complete 2.13 variant family (GREEN)** — `d0ad5e6` (`feat`)

## Files Created/Modified

- `src/totem/hardware/builtin/display/drivers/waveshare_2in13*.py` — Seven concrete provider-owned Waveshare variants.
- `tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py` — Exact variant inventory and mock transport/frame/orientation coverage.

## Verification

- ` .venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py -x` — 16 passed.
- ` .venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_core.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 13 passed.
- ` .venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py tests/unit/hardware_runtime/test_builtin_display_core.py tests/unit/hardware_runtime/test_import_boundaries.py tests/unit/hardware_runtime/test_catalog_claim_tracer.py tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_broker.py -x` — 47 passed.
- ` .venv/bin/python -m pytest tests/unit/hardware_runtime -x` — 116 passed.
- ` .venv/bin/python -m compileall -q src/totem/hardware/builtin/display/drivers` and `git diff --check` — passed.
- Source audit found no legacy owner imports, device paths, or direct `spidev`/`gpiod` imports in the new variant modules.

## Decisions Made

- All variants use the provider-owned injected base; transport loading remains deferred until initialization and tests supply recording mocks.
- Pi 5 chip-select modes are separate concrete variants: hardware CS has no software toggle and software CS brackets each transfer.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 13 can migrate the remaining display variants using the same provider-owned, mock-only inventory pattern.
- No device allocation, SSH, deployment, network contact, GPIO/SPI access, or hardware-marked test was performed.

## Self-Check: PASSED

- All seven provider variant modules and the exhaustive test file exist.
- Task commits `e4ce428` and `d0ad5e6` exist on `refactor/hardware-ontology`.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
