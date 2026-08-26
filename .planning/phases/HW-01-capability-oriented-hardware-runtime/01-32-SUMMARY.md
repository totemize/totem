---
phase: HW-01-capability-oriented-hardware-runtime
plan: "32"
subsystem: deployment startup composition
tags: [python, cli, toml, environment, systemd, hardware-runtime, pytest]
requires:
  - phase: HW-01-25
    provides: Screen bus-client boundary and retained screen command behavior.
  - phase: HW-01-29
    provides: Display/power client-only compatibility facades.
  - phase: HW-01-30
    provides: NFC/storage client-only compatibility facades.
  - phase: HW-01-31
    provides: Wi-Fi/Bluetooth client-only compatibility facades.
provides:
  - `totem` and `totem-api` startup composition over one injected canonical runtime.
  - Typed TOML configuration plus outward-only legacy environment translation.
  - Static package-entry-point, screen-client, and systemd unit contract coverage.
affects: [HW-01-33, deployment, systemd, legacy-device-facades]
tech-stack:
  added: []
  patterns:
    - Startup parses compatibility environment only in `totem.__main__`, then passes typed state inward.
    - Both deployed API commands supply Uvicorn with a composed application object, never an import string that can bypass composition.
key-files:
  created:
    - tests/unit/test_cli_compat.py
    - tests/unit/test_systemd_contracts.py
  modified:
    - src/totem/__main__.py
    - src/totem/api/app.py
key-decisions:
  - "An injected RuntimeConfig takes precedence over an optional TOML path, preserving testable controlled-start composition."
  - "The totem-api entry point lazily reuses totem.__main__.compose_application so both deployed API command names start one canonical runtime shape."
patterns-established:
  - "Deployment contracts are tested statically through package metadata and unit text, with local fake runtime lifespans instead of service/device contact."
requirements-completed: [HWR-04, API-04, TST-04]
coverage:
  - id: D1
    description: The totem and totem-api commands compose a single typed, injected canonical runtime and expose legacy settings only at the outward boundary.
    requirement: HWR-04
    verification:
      - kind: unit
        ref: tests/unit/test_cli_compat.py
        status: pass
    human_judgment: false
  - id: D2
    description: Existing package command names, screen client behavior, and systemd service identity/order/ExecStart contracts remain stable.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_systemd_contracts.py
        status: pass
    human_judgment: false
  - id: D3
    description: Startup and canonical hardware modules retain their one-way compatibility/import boundary.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
metrics:
  duration: "17m"
  completed: "2026-08-26"
status: complete
---

# Phase HW-01 Plan 32: Deployment Command and Systemd Composition Summary

**The deployed `totem` and `totem-api` commands now compose one typed canonical runtime application while preserving legacy environment, package entry-point, screen-client, and systemd contracts.**

## Performance

- **Duration:** 17 min
- **Completed:** 2026-08-26T18:06:39Z
- **Tasks:** 1/1
- **Files modified:** 6

## Accomplishments

- Added optional typed TOML startup input and explicit injected-config precedence to the `totem` command.
- Moved deployed `TOTEM_*` parsing out of the API application and into the outward startup boundary.
- Routed `totem` and `totem-api` through the same composed application object, retaining all three published scripts and unchanged screen/systemd contracts.
- Added local-only one-owner, invalid-binding, entry-point, static systemd, and import-boundary coverage.

## Task Commits

1. **Task 1: Compose preserved commands and service contracts around one owner (RED)** — `795f8d4` (`test`)
2. **Task 1: Compose preserved commands and service contracts around one owner (GREEN)** — `d8d4d40` (`feat`)
3. **Task 1: Verify deployed entry point resolution** — `0203d14` (`test`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_cli_compat.py tests/unit/test_systemd_contracts.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 15 passed.
- `.venv/bin/python -m pytest tests/unit/test_api_facades.py tests/unit/hardware_runtime/test_config.py -x` — 9 passed.
- `.venv/bin/python -m compileall -q src/totem/__main__.py src/totem/api/app.py src/totem/screen/__main__.py` — passed.
- `.venv/bin/python -m totem --help` and `git diff --check` — passed.
- All checks used local config files, fake runtimes, source/unit text, and in-process application seams only. No SSH, network, deployment, systemd operation, live service, device, radio, USB/serial/I2C/GPIO, or hardware-marked test was contacted.

## Files Created/Modified

- `src/totem/__main__.py` — Typed composition of runtime config, legacy inputs, and the canonical runtime owner.
- `src/totem/api/app.py` — Receives already-translated startup state; `totem-api` invokes shared composition.
- `tests/unit/test_cli_compat.py` — Local fake-runtime lifecycle, config precedence, invalid binding, and command invocation coverage.
- `tests/unit/test_systemd_contracts.py` — Static package script, service, screen-client, and entry-point resolution contracts.

## Decisions Made

- Preserve the API's deployment-facing command names while centralizing runtime composition at `totem.__main__.compose_application`.
- Keep service verification static/local: identity, ordering, and `ExecStart` text are contracts, not authorization to restart a service.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project continuity] Recorded the required session journal entry**
- **Found during:** Plan close-out.
- **Issue:** `AGENTS.md` requires completed sessions in the dated journal and journal index.
- **Fix:** Recorded Plan 01-32's local-only outcome in `.journey/journal/2026-08-26.md` and `.journey/README.md`.
- **Files modified:** `.journey/journal/2026-08-26.md`, `.journey/README.md`.
- **Verification:** The dated entry and index row identify the plan and local-only checks.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (Rule 2 project continuity). **Impact:** Documentation-only; no runtime ownership or deployment scope expanded.

## Issues Encountered

The initial local fake runtime did not expose the canonical `handle` seam expected by `HardwareBus`; the test fake was completed before GREEN verification. Production composition always supplies `HardwareRuntime`, which implements this seam.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no service configuration or device action was performed.

## Next Phase Readiness

- Phase 01-33 can carry these command, unit, and one-owner checks into final local regression.
- Pi measurements and any deployed-default changes remain explicit, separate hardware allocation gates.

## TDD Gate Compliance

- RED `795f8d4` failed as expected because startup composition did not expose the typed config/factory seam.
- GREEN `d8d4d40` passed the focused local contract suite; `0203d14` added direct resolution coverage for all three published entry points.

## Self-Check: PASSED

- Found the declared startup, API, CLI-contract, systemd-contract, and summary files.
- Found TDD commits `795f8d4`, `d8d4d40`, and `0203d14` in repository history.
