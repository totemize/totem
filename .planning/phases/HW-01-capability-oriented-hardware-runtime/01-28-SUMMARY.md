---
phase: HW-01-capability-oriented-hardware-runtime
plan: "28"
subsystem: hardware compatibility registry and lifecycle contracts
tags: [catalog, compatibility, driver-api, lifecycle, import-boundary]
requires:
  - phase: HW-01-27
    provides: client-only manager facades and canonical hardware client
provides:
  - Catalog-backed legacy DriverRegistry with no provider-import or resource-ownership path.
  - Explicit public lifecycle aliases and structural legacy driver-contract coverage.
  - Fixture-plugin regression proving no central registry edit or provider import is needed.
affects: [HW-01-29, HW-01-30, HW-01-31, legacy-device-facades]
tech-stack:
  added: []
  patterns:
    - Legacy registry records are projections of immutable catalog metadata.
    - Legacy loading can only request an already-ready canonical runtime handle.
key-files:
  created:
    - tests/unit/test_registry_facade.py
  modified:
    - src/totem/devices/contracts.py
    - src/totem/devices/registry.py
    - tests/unit/test_driver_contracts.py
    - tests/unit/test_driver_registry.py
    - tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py
    - tests/unit/hardware_runtime/test_builtin_wifi.py
    - tests/unit/test_wifi_provider_compat.py
key-decisions:
  - "Keep historical registry constructors and error names import-compatible while ignoring their static interface/spec inputs."
  - "Alias DriverState to the public BindingState and remove DeviceDriver attribute inference and lifecycle ownership."
patterns-established:
  - "Compatibility lookup reads catalog metadata and delegates only through an injected runtime handle port."
requirements-completed: [API-04, API-05, TST-04]
metrics:
  duration: "18m"
  completed: "2026-08-26"
status: complete
---

# Phase HW-01 Plan 28: Catalog-Only Legacy Registry Facade Summary

Legacy registry and lifecycle imports now present catalog metadata and explicit public lifecycle state without loading, constructing, or owning concrete providers.

## Tasks Completed

1. Replaced `DriverRegistry` provider imports and allow-list execution with catalog projections and injected opaque runtime-handle delegation.
2. Replaced inferred `DeviceDriver` lifecycle behavior with a no-behavior compatibility protocol and explicit `BindingState`-based health projection.
3. Converted the accumulated display, UPS, and NFC inheritance assertions into structural contract checks and closed Windows entries 10, 12, and 13.

## Verification

- `.venv/bin/python -m pytest tests/unit/test_driver_registry.py tests/unit/test_driver_contracts.py tests/unit/test_registry_facade.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 50 passed.
- `.venv/bin/python -m compileall -q src/totem packages/totem-driver-api/src/totem_driver_api` — passed.
- `git diff --check` — passed.
- Registry source audit found no `importlib`, built-in provider imports, resource claim/release calls, or registry lifecycle ownership methods.
- Follow-up focused driver-contract, registry, facade, display-compatibility, and import-boundary suite — 84 passed.
- Full `.venv/bin/python -m pytest tests/unit -x -q --tb=short` progressed through the formerly order-dependent driver identity assertion and reached 332 passed before the pre-existing client-only manager migration failure recorded below.
- Follow-up focused Wi-Fi provider, facade, registry, and import-boundary suite — 37 passed.
- Final `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — 440 passed.

## Decisions Made

- `DriverRegistry.load()` can only obtain an existing canonical runtime handle through `handle(capability_id, binding_id)`; it cannot resolve hardware, claim resources, or instantiate providers.
- Historical static `DriverSpec` lists are accepted only to keep imports viable until Plans 29–31 migrate their family wrappers; catalog metadata is the sole registry record source.
- Public `BindingState` is the authoritative lifecycle vocabulary; legacy `NEW`/`MOCK` attribute inference is retired.

## Deviations from Plan

### Auto-fixed Issues

1. [Rule 1 - Bug] Retired obsolete display transport implementation assertions
   - **Found during:** Task 1 verification
   - **Issue:** Legacy contract tests patched removed module globals and expected removed GPIO fallback behavior, causing either import failures or real-time sleeps after the provider clean break.
   - **Fix:** Targeted the canonical provider only where behavior remains relevant, used injected sleep, and removed obsolete ownership assertions.
   - **Files modified:** `tests/unit/test_driver_contracts.py`
   - **Verification:** focused 50-test suite passed.
   - **Commit:** `710d3eb`

**Total deviations:** 1 auto-fixed (Rule 1). **Impact:** preserves the clean-break contract without restoring legacy hardware ownership.

## Integration Repair

- A provider import-safety test removed canonical Waveshare modules from `sys.modules` without restoring the parent package attribute. That test-only mutation could leave a legacy facade holding the old `Driver` class while a later canonical import created a new class of the same qualified name.
- `_fresh_variant_import()` now restores both cache entry and parent-package attribute in `finally`, and an order-proof regression imports the legacy generic facade before probing a fresh V2 module.
- Commit: `4cdfaaf`.

- The Wi-Fi catalog import probe had the same cache-restoration defect: evicting `network_manager_wifi` left a legacy package facade holding the former module object. The probe now restores every evicted module and its parent attribute, and an ordered regression proves direct legacy package re-exports retain canonical module identity.
- The Wi-Fi inventory also reloads each one-line facade before comparing identities, preventing a sibling legacy-child import from replacing a package re-export with the legacy module object.
- Commit: `a9c3642`.

## Deferred Issues

None. The prior client-only manager test expectations were repaired independently in Plan 01-27 before this final full-suite run.

## Known Stubs

None.

## Self-Check: PASSED

- Required source and test files exist.
- RED commit `40b3fb5` and GREEN commit `710d3eb` exist in git history.
- Integration repair commit `4cdfaaf` exists in git history.
- Wi-Fi integration repair commit `a9c3642` exists in git history.
