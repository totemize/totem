---
phase: HW-01-capability-oriented-hardware-runtime
plan: "29"
subsystem: hardware-compatibility
tags: [python, display, power, capability-client, compatibility-facade, pytest]
requires:
  - phase: HW-01-26
    provides: LegacyHardwareClient translation over the canonical hardware bus.
  - phase: HW-01-28
    provides: Catalog-only legacy registry and explicit lifecycle compatibility contracts.
provides:
  - Display and UPS family wrappers that delegate operations only through an injected canonical client.
  - Facade-local lifecycle and close behavior with no provider, runtime, resource, or hardware ownership path.
  - Focused fake-client and AST ownership coverage for display and power wrapper imports.
affects: [HW-01-30, HW-01-31, legacy-device-facades, hardware-api]
tech-stack:
  added: []
  patterns:
    - Historical family wrappers retain selection inputs as inert compatibility configuration and accept an injected LegacyHardwareClient.
    - Wrapper lifecycle state is local compatibility state; shared canonical client and runtime ownership are never closed by a facade.
key-files:
  created:
    - tests/unit/test_device_display_power_facades.py
  modified:
    - src/totem/devices/display/__init__.py
    - src/totem/devices/display/display.py
    - src/totem/devices/ups/ups.py
    - tests/unit/test_pisugar2.py
key-decisions:
  - "Display and UPS selection names remain inert compatibility configuration; wrappers neither probe nor select a local driver."
  - "Initialize and close are facade-local compatibility transitions, while display writes and power telemetry use the shared canonical client."
patterns-established:
  - "Family facade clean-break tests use recording client fakes plus AST import/probe audits, never hardware transport fixtures."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Legacy EInk and UPS imports retain caller-facing constructors and operations while dispatching display writes and telemetry through an injected canonical client.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_device_display_power_facades.py#test_display_constructor_and_operations_only_delegate_to_an_injected_client
        status: pass
      - kind: unit
        ref: tests/unit/test_device_display_power_facades.py#test_ups_constructor_lifecycle_and_telemetry_only_use_the_client
        status: pass
    human_judgment: false
  - id: D2
    description: Display and UPS wrappers own no driver registry, provider, hardware probe, lease, runtime, or shared-client shutdown path.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_device_display_power_facades.py#test_wrapper_sources_have_no_provider_registry_transport_or_hardware_probe
        status: pass
      - kind: unit
        ref: tests/unit/test_device_display_power_facades.py#test_close_is_facade_local_and_preserves_shared_client_access
        status: pass
    human_judgment: false
  - id: D3
    description: Canonical hardware modules retain their one-way import boundary after display and power facade migration.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
metrics:
  duration: "2m"
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 29: Display and Power Wrapper Delegation Summary

**Legacy EInk and UPS family names now keep their public calls while delegating display writes and telemetry solely through a shared canonical hardware client.**

## Performance

- **Duration:** 2m
- **Started:** 2026-08-26T17:37:13Z
- **Completed:** 2026-08-26T17:39:17Z
- **Tasks:** 1/1
- **Files modified:** 4

## Accomplishments

- Replaced display and UPS family driver loading, local detection, and direct driver operation with injected `LegacyHardwareClient` delegation.
- Kept historical driver-name and mock inputs as inert outward-boundary configuration; initialization and close are local facade transitions only.
- Exported the public display compatibility classes and added fake-backed operation, shared-client, public-import, and AST ownership coverage.

## Task Commits

1. **Task 1: Delegate display and power wrappers to canonical capabilities (RED)** — `c441046` (`test`)
2. **Task 1: Delegate display and power wrappers to canonical capabilities (GREEN)** — `5b564c9` (`feat`)
3. **Integration repair: Keep configured I2C selection at the canonical power seam** — `9bdc04e` (`test`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_device_display_power_facades.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 13 passed.
- `.venv/bin/python -m compileall -q src/totem/devices/display src/totem/devices/ups` — passed.
- `git diff --check` — passed.
- Source audit found no wrapper registry/provider/transport imports, hardware probes, or direct device paths. All verification used injected local fakes only; no SSH, network, deployment, live service, USB/serial/I2C/GPIO, real device, or hardware-marked test was contacted.
- `.venv/bin/python -m pytest tests/unit/test_device_display_power_facades.py tests/unit/test_pisugar2.py tests/unit/test_waveshare_ups_hat_c.py tests/unit/hardware_runtime/test_builtin_power.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 30 passed.
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — 458 passed.

## Files Created/Modified

- `src/totem/devices/display/__init__.py` — Public compatibility exports for `EInk` and `EInkDeviceInterface`.
- `src/totem/devices/display/display.py` — Client-only display facade with local initialization and close state.
- `src/totem/devices/ups/ups.py` — Client-only UPS telemetry facade with local initialization and close state.
- `tests/unit/test_device_display_power_facades.py` — Recording-client and AST ownership regression coverage.
- `tests/unit/test_pisugar2.py` — Canonical injected PiSugar configured-I2C selection regression.

## Decisions Made

- Preserve driver-name and mock flags as inert compatibility configuration rather than using them to load, detect, or initialize a local driver.
- Keep initialization and close facade-local so multiple wrappers can share one canonical client and the runtime remains its sole lifecycle owner.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Stale ownership assertion] Kept configured I2C selection at the canonical PiSugar seam**
- **Found during:** Post-plan full unit-suite integration after 361 passing tests.
- **Issue:** A historical `UPS._detect_hardware()` assertion required the client-only facade to inspect `/dev/i2c-*`, contradicting the completed clean-break contract.
- **Fix:** Replaced it with an injected-transport canonical PiSugar test that proves `TOTEM_I2C_BUS` selects bus 7 without contacting I2C.
- **Files modified:** `tests/unit/test_pisugar2.py`
- **Verification:** focused display/power/UPS/import suite passed 30 tests; full unit suite passed 458 tests.
- **Committed in:** `9bdc04e`

**2. [Rule 2 - Project continuity] Recorded the required session journal entry**
- **Found during:** Plan close-out.
- **Issue:** `AGENTS.md` requires each completed session to be added to the project journal and index.
- **Fix:** Added the execution result to the dated journal and journal index.
- **Files modified:** `.journey/journal/2026-08-26.md`, `.journey/README.md`
- **Verification:** Journal entry and index row identify Plan 01-29 and its local-only verification.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 stale test, 1 Rule 2 project-continuity requirement).
**Impact on plan:** The repair eliminates an obsolete facade ownership demand; display/power runtime ownership stays unchanged.

## Issues Encountered

The full suite initially failed after 361 passing tests because an obsolete PiSugar compatibility test expected the migrated UPS facade to probe local I2C. The assertion now verifies the canonical injected driver instead, and the full 458-test unit suite passes.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Display and power family wrappers no longer provide a local hardware ownership backdoor.
- Later family-wrapper plans can follow the injected-client and AST ownership pattern.

## TDD Gate Compliance

- RED `c441046` failed during collection because the public display package did not yet export the facade and wrappers lacked the injected-client seam.
- GREEN `5b564c9` exported the facade and completed client-only delegation; the focused suite passed.

## Self-Check: PASSED

- Found the declared display, UPS, and facade-test files on disk.
- Found TDD commits `c441046` and `5b564c9` in repository history.
- Found integration repair commit `9bdc04e` in repository history.
