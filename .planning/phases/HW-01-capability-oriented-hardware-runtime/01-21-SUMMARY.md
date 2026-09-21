---
phase: HW-01-capability-oriented-hardware-runtime
plan: "21"
subsystem: hardware-wifi-compatibility
tags: [wifi, compatibility, imports, ast, pytest]
requires:
  - phase: HW-01-20
    provides: Canonical built-in Wi-Fi provider, shared radio support, and driver implementations.
provides:
  - Exhaustive import-only facades for all historical Wi-Fi/shared-support modules.
  - Object-identity, available-signature, and AST tests that prevent legacy backend ownership from returning.
affects: [HW-01-22, compatibility-facades, legacy-network-imports]
tech-stack:
  added: []
  patterns:
    - Legacy hardware paths use a single wildcard import from their canonical module so public object identity is preserved.
    - Compatibility inventories validate package and module facades from source ASTs as well as imported public surfaces.
key-files:
  created:
    - tests/unit/test_wifi_provider_compat.py
  modified:
    - src/totem/devices/network/dbus_runtime.py
    - src/totem/devices/network/errors.py
    - src/totem/devices/network/models.py
    - src/totem/devices/network/nan.py
    - src/totem/devices/network/drivers/__init__.py
    - src/totem/devices/network/drivers/mock_wifi.py
    - src/totem/devices/network/drivers/network_manager_wifi.py
    - src/totem/devices/network/drivers/rpi5_onboard_wifi.py
    - src/totem/devices/network/drivers/usb_wifi_adapter.py
key-decisions:
  - "Each historical Wi-Fi/support path re-exports its complete canonical public surface with a single import-only statement."
  - "Compatibility verification treats package __init__.py facades as first-class inventory members and compares signatures only when Python exposes one."
patterns-established:
  - "Legacy module migrations are protected by a fixed path-to-canonical inventory plus AST-only body assertions."
requirements-completed: [API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Historical Wi-Fi and shared-support import paths resolve to exact canonical objects without deprecation warnings or local backend ownership.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_wifi_provider_compat.py#test_wifi_legacy_modules_are_exhaustive_direct_reexports
        status: pass
    human_judgment: false
  - id: D2
    description: All nine legacy Wi-Fi/support facade sources contain only a direct canonical wildcard import.
    requirement: API-05
    verification:
      - kind: unit
        ref: tests/unit/test_wifi_provider_compat.py#test_wifi_legacy_module_bodies_only_import_the_canonical_module
        status: pass
    human_judgment: false
  - id: D3
    description: Canonical hardware imports do not cross back into legacy device ownership.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_import_boundaries.py
        status: pass
    human_judgment: false
duration: 3min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 21: Wi-Fi Compatibility Facades Summary

**Nine historical Wi-Fi and shared-radio support paths now preserve exact canonical objects through import-only compatibility facades, with AST guards against restored backend ownership.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-08-26T14:50:04Z
- **Completed:** 2026-08-26T14:53:04Z
- **Tasks:** 1/1
- **Files modified:** 10

## Accomplishments

- Replaced legacy D-Bus, errors, models, NAN, and five Wi-Fi driver paths with direct canonical re-exports.
- Added an exhaustive fixed inventory that asserts public-name parity, exact identity, available signatures, and no deprecation warning for every legacy import.
- Added AST enforcement proving each compatibility facade has exactly one direct canonical wildcard import and no D-Bus, provider, selection, session, or resource-owning body.

## Task Commits

1. **Task 1: Replace all Wi-Fi/support legacy modules with re-exports (RED)** — `cda6bb3` (`test`)
2. **Task 1: Replace all Wi-Fi/support legacy modules with re-exports (GREEN)** — `af0ce13` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_wifi_provider_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 25 passed.
- `.venv/bin/python -m compileall -q src/totem/devices/network` — passed.
- `git diff --check` — passed.
- All checks used deterministic local imports and mocked seams only; no hardware, radio, D-Bus service, network, device, or deployment contact occurred.

## Files Created/Modified

- `src/totem/devices/network/{dbus_runtime.py,errors.py,models.py,nan.py}` — Import-only facades for canonical shared radio support.
- `src/totem/devices/network/drivers/{__init__.py,mock_wifi.py,network_manager_wifi.py,rpi5_onboard_wifi.py,usb_wifi_adapter.py}` — Import-only facades for canonical Wi-Fi drivers.
- `tests/unit/test_wifi_provider_compat.py` — Exhaustive identity/signature/deprecation and AST compatibility inventory.

## Decisions Made

- Preserve the whole canonical public surface rather than curate legacy symbol lists, so all existing imported objects retain exact identity.
- Enforce source-level import-only bodies to make legacy ownership regressions fail before any D-Bus/session code can run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hardened the compatibility inventory for package facades and non-inspectable builtins**
- **Found during:** Task 1 GREEN verification.
- **Issue:** The first inventory treated the package facade as a `.py` module and assumed every callable exposes an inspectable Python signature; package `__init__.py` and builtin exceptions violated those assumptions.
- **Fix:** Resolved package facades to `__init__.py` and compare signatures only where `inspect.signature` is available, while retaining identity checks for every public object.
- **Files modified:** `tests/unit/test_wifi_provider_compat.py`.
- **Verification:** Focused compatibility and import-boundary suite passed 25 tests.
- **Committed in:** `af0ce13`.

---

**Total deviations:** 1 auto-fixed (1 Rule 1 test-inventory bug).
**Impact on plan:** The correction makes the exhaustive inventory valid for every requested facade without weakening any ownership or identity assertion.

## Issues Encountered

None.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Canonical Wi-Fi ownership is now protected from legacy-module regressions and remaining hardware migration plans can rely on these facades.
- No device, SSH, network, D-Bus service, radio, USB/serial/I2C/GPIO, deployment, or hardware-marked test was contacted.

## Self-Check: PASSED

- Found all nine compatibility module files and the exhaustive test file on disk.
- Found TDD commits `cda6bb3` and `af0ce13` in git history.
