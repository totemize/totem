---
phase: HW-01-capability-oriented-hardware-runtime
plan: "11"
subsystem: hardware-runtime
tags: [python, display, driver-provider, manifest, dual-host, mock-transport]
requires:
  - phase: HW-01-10
    provides: Process/in-process host conformance and manifest-first runtime composition
provides:
  - Import-free built-in display manifest and driver entry point
  - Variant-neutral child-only display provider with declared SPI/GPIO claim checks
  - Injected-transport common Waveshare 2.13 framebuffer base
affects: [display-variants, display-compatibility, runtime-composition]
tech-stack:
  added: []
  patterns: [manifest-before-provider-import, child-only transport injection, profile-selected display family]
key-files:
  created:
    - src/totem/hardware/builtin/display/provider.py
    - src/totem/hardware/builtin/display/totem-driver-manifest.json
    - src/totem/hardware/builtin/display/drivers/_waveshare_2in13_base.py
    - tests/unit/hardware_runtime/test_builtin_display_core.py
  modified:
    - pyproject.toml
key-decisions:
  - "The manifest resolves the Waveshare 2.13 family from data-only profile evidence; a configured panel variant remains a child-composition concern."
  - "Display provider construction is side-effect-free and accepts only injected transports after exact SPI/GPIO claim validation."
patterns-established:
  - "Built-in driver manifests are package data registered through the totem.hardware.drivers entry-point group."
  - "Display core tests use mock transports and real process/in-process host envelopes without device contact."
requirements-completed: [HWR-02, SPI-06]
coverage:
  - id: D1
    description: Import-free built-in display manifest resolves one generic frame-sink provider only after data-only profile and complete declared resource evidence.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_core.py
        status: pass
      - kind: other
        ref: local wheel package-data and entry-point inspection
        status: pass
    human_judgment: false
  - id: D2
    description: Display provider validates the selected 2.13 variant, complete SPI/GPIO claims, geometry, and media before injected transport I/O, with matching real process and in-process transcripts.
    requirement: SPI-06
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_display_core.py#test_core_provider_has_matching_in_process_and_process_conformance_with_mock_transport
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime -x
        status: pass
    human_judgment: false
metrics:
  duration: 5m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 11: Built-In Display Provider Core Summary

**A manifest-first, variant-neutral display provider now exposes `display.frame-sink@1` through both host modes while keeping panel transports and concrete variants child-only.**

## Performance

- **Duration:** 5m
- **Tasks:** 1/1
- **Files modified:** 8

## Accomplishments

- Registered the built-in display distribution and package-data manifest without loading provider or hardware modules during catalog inspection.
- Added a side-effect-free provider seam that requires a declared 2.13 panel variant, complete SPI/GPIO claims, valid mono frame geometry, and an injected transport before I/O.
- Moved the common Waveshare 2.13 framebuffer/SPI/GPIO lifecycle into the provider package with explicit mock/injected transport support and the retained 180-degree mount contract.
- Proved equivalent process and in-process logical transcripts against mock transports; no GPIO, SPI, display, device, SSH, network, deployment, or hardware-marked test was contacted.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_core.py -x` — passed (6 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (100 tests).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (236 tests).
- `.venv/bin/python -m compileall -q src/totem/hardware/builtin` — passed.
- Local wheel manifest/entry-point inspection, ASVS SEC-01/04/06 source audit, and `git diff --check` — passed.

## TDD Gate Compliance

- RED `02d9dc0` added the failing manifest-first selection, mock transport, common-base, and dual-host conformance contract.
- GREEN `1cc1fd1` added the registered manifest, child provider core, injected common base, and focused tests.
- Follow-up `dd0b05a` corrected the manifest predicate to resolve the 2.13 family rather than pinning it to the V4 panel.

## Task Commits

1. **Task 1: Create the display provider core and common panel contract** — `02d9dc0` (RED), `1cc1fd1` (GREEN), `dd0b05a` (fix)

## Files Created/Modified

- `pyproject.toml` — registers the built-in display driver entry point and packages its manifest.
- `src/totem/hardware/builtin/display/provider.py` — validates selected variants, claims, frames, and injected transport before I/O.
- `src/totem/hardware/builtin/display/totem-driver-manifest.json` — declares `display.frame-sink@1`, profile evidence, typed config, and GPIO/SPI claims.
- `src/totem/hardware/builtin/display/drivers/_waveshare_2in13_base.py` — provider-owned common injected transport/framebuffer lifecycle.
- `tests/unit/hardware_runtime/test_builtin_display_core.py` — import boundary, selection, ambiguity, no-I/O, host conformance, and common-base coverage.

## Decisions Made

- The profile identifies the Waveshare 2.13 family; the explicit `panel_variant` configuration determines the eventual concrete child variant without a core device-model switch.
- The provider does not import, probe, or open hardware on construction. Concrete panel and transport composition stays in the child after runtime claim acquisition.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Kept the manifest selector variant-neutral**
- **Found during:** Task 1 acceptance review.
- **Issue:** The initial profile predicate selected only the V4 label, which would have made the family provider falsely variant-specific before the planned concrete variant migrations.
- **Fix:** Changed the manifest predicate to the `waveshare-2in13` family and retained the explicit panel variant in typed child configuration.
- **Files modified:** `src/totem/hardware/builtin/display/totem-driver-manifest.json`, `tests/unit/hardware_runtime/test_builtin_display_core.py`.
- **Verification:** Focused display-core tests pass, including profile resolution and ambiguous selection with no provider import.
- **Committed in:** `dd0b05a`.

**Total deviations:** 1 auto-fixed (1 Rule 1 bug). **Impact:** Correctness-only; preserves the plan's independent concrete-variant migration boundary.

## Issues Encountered

- Black and Flake8 are not installed in the project venv, so their scoped checks were unavailable; neither is a plan verification gate. All required pytest, wheel, compile, import-boundary, source-audit, and diff checks passed.

## Known Stubs

None. Optional constructor transport/variant values intentionally reject requests until controlled child composition supplies a selected variant, complete claims, and an injected transport.

## User Setup Required

None — all verification used in-memory mock transports, local child processes, and package metadata. No external service or physical hardware setup is needed.

## Next Phase Readiness

Plans 12 and 13 can migrate concrete 2.13 and auxiliary panel modules into the provider package while preserving the established manifest-first and injected-transport boundaries.

## Self-Check: PASSED

- Provider, manifest, common-base, and focused core test files exist in the worktree.
- RED/GREEN/fix commits `02d9dc0`, `1cc1fd1`, and `dd0b05a` exist in git history.
- No stubs, skipped tests, or unrun required verification commands remain.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
