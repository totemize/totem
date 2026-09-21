---
phase: HW-01-capability-oriented-hardware-runtime
plan: "22"
subsystem: hardware-bluetooth-provider
tags: [bluetooth, bluez, l2cap, gatt, radio, dual-host, pytest]
requires:
  - phase: HW-01-19
    provides: Versioned Bluetooth contracts and shared-PHY coexistence policy.
  - phase: HW-01-20
    provides: Import-safe radio provider and matching dual-host dispatch patterns.
  - phase: HW-01-21
    provides: Import-only compatibility facade conventions.
provides:
  - Import-safe built-in Bluetooth provider manifest and entry point.
  - Lease-gated BlueZ, mock Bluetooth, GATT, and L2CAP session ownership.
  - Matching process and in-process Bluetooth message dispatch using injected mocks.
affects: [HW-01-23, radio-providers, compatibility-facades, runtime-broker]
tech-stack:
  added: []
  patterns:
    - Provider-local Bluetooth lifecycle validates leased D-Bus, adapter, and PHY facts before backend composition.
    - Multi-provider built-in packages use provider-local package-data manifests without loading entry points.
key-files:
  created:
    - src/totem/hardware/builtin/radio/bluetooth_provider.py
    - src/totem/hardware/builtin/radio/bluetooth-manifest.json
    - src/totem/hardware/builtin/radio/l2cap.py
    - src/totem/hardware/builtin/radio/drivers/bluez.py
    - src/totem/hardware/builtin/radio/drivers/mock_bluetooth.py
    - tests/unit/hardware_runtime/test_builtin_bluetooth.py
  modified:
    - src/totem/hardware/hosts/in_process.py
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/catalog/manifests.py
    - src/totem/devices/network/bluetooth.py
key-decisions:
  - "BlueZ composition accepts only leased D-Bus, adapter, and PHY facts; Wi-Fi ownership is never imported or shared."
  - "A provider-local manifest takes precedence inside a package that exposes multiple independent built-in providers."
patterns-established:
  - "Bluetooth public messages use the same narrow process and in-process host dispatcher as Wi-Fi while preserving provider-local lifecycle state."
requirements-completed: [API-02, RUN-03, TST-04]
coverage:
  - id: D1
    description: Built-in Bluetooth is cataloged without importing BlueZ and validates exact leased claims before backend composition.
    requirement: API-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_bluetooth.py#test_catalog_reads_bluetooth_manifest_without_importing_bluez_provider
        status: pass
    human_judgment: false
  - id: D2
    description: Mock Bluetooth retains radio, discovery, advertising, GATT, and L2CAP behavior through matching process and in-process hosts.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_bluetooth.py#test_bluetooth_has_matching_dual_host_contract_using_mock_session_only
        status: pass
    human_judgment: false
  - id: D3
    description: Bluetooth restart remains provider-local while incompatible shared-PHY modes are rejected by broker policy before provider work.
    requirement: RUN-03
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_bluetooth.py#test_bluetooth_failure_restart_and_shared_phy_denial_are_provider_local
        status: pass
    human_judgment: false
duration: 8min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 22: Independent Bluetooth Provider Summary

**BlueZ Bluetooth is now an import-safe, lease-gated provider with local lifecycle isolation, mock GATT/L2CAP parity, and shared-PHY coordination only through broker policy.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-26T15:01:07Z
- **Completed:** 2026-08-26T15:09:25Z
- **Tasks:** 1/1
- **Files modified:** 16

## Accomplishments

- Published a package-data Bluetooth declaration, catalog entry point, and side-effect-free provider factory.
- Relocated BlueZ, deterministic mock Bluetooth, and bounded L2CAP ownership into canonical built-in radio modules.
- Added lease validation, local restart/quarantine state, Bluetooth public dispatch, and process/in-process conformance checks.
- Kept historical BlueZ, mock Bluetooth, and L2CAP paths as canonical re-exports.

## Task Commits

1. **Task 1: Catalog BlueZ Bluetooth with independent lifecycle and claims (RED)** — `36554f6` (`test`)
2. **Task 1: Catalog BlueZ Bluetooth with independent lifecycle and claims (GREEN)** — `22bacae` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_bluetooth.py tests/unit/test_radio_primitives.py -k 'bluetooth or bluez or l2cap or gatt' -x` — 16 passed, 18 deselected.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py tests/unit/hardware_runtime/test_manifest.py -x` — 8 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_manifest.py tests/unit/hardware_runtime/test_catalog_claim_tracer.py -x -q --tb=short` — 7 passed.
- `.venv/bin/python -m compileall -q src/totem/hardware/builtin/radio src/totem/hardware/hosts src/totem/devices/network` and `git diff --check` — passed.
- All verification used deterministic local mocks and injected D-Bus seams; no device, radio, service, network, or hardware-marked test was contacted.

## Files Created/Modified

- `src/totem/hardware/builtin/radio/{bluetooth_provider.py,bluetooth-manifest.json}` — Lease-gated provider composition and import-free metadata.
- `src/totem/hardware/builtin/radio/{l2cap.py,drivers/bluez.py,drivers/mock_bluetooth.py}` — Canonical BlueZ, deterministic Bluetooth, and bounded L2CAP behavior.
- `src/totem/hardware/hosts/{worker.py,in_process.py}` — Bluetooth public-message forwarding under both hosts.
- `src/totem/devices/network/{bluetooth.py,l2cap.py,drivers/bluez.py,drivers/mock_bluetooth.py}` — Compatibility ownership bridge and thin canonical facades.
- `tests/unit/hardware_runtime/test_builtin_bluetooth.py` — Catalog, claim validation, primitive, lifecycle, coexistence, dual-host, and re-export coverage.

## Decisions Made

- Validate BlueZ D-Bus service, adapter, and PHY claims before constructing a driver; caller messages never choose those identities.
- Keep Bluetooth's lifecycle and process group local to the provider, leaving all Wi-Fi coexistence decisions in the broker's explicit shared-PHY policy.
- Prefer provider-local metadata only when present, retaining the established single-provider manifest behavior for other distributions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added provider-local manifest selection for multi-provider packages**
- **Found during:** Task 1 GREEN catalog verification.
- **Issue:** The catalog only recognized one fixed `totem-driver-manifest.json` per package, so the Bluetooth entry point could not discover its own declaration beside Wi-Fi's manifest.
- **Fix:** Added a provider-local `*-manifest.json` lookup that takes precedence when present and falls back to the established package manifest otherwise.
- **Files modified:** `src/totem/hardware/catalog/manifests.py`, `tests/unit/hardware_runtime/test_builtin_bluetooth.py`.
- **Verification:** Bluetooth import-free catalog and existing manifest/catalog suites passed.
- **Committed in:** `22bacae`.

**2. [Rule 3 - Blocking] Restored legacy mock-manager compatibility through canonical radio interfaces**
- **Found during:** Task 1 GREEN primitive regression verification.
- **Issue:** The historical `NetworkManager` fixture rejected the relocated mock Wi-Fi class and then lacked the standard mock lifecycle property, blocking Bluetooth primitive regression coverage.
- **Fix:** Pointed the legacy Wi-Fi interface at its canonical counterpart and supplied the minimal common close/mock lifecycle behavior in canonical radio interfaces.
- **Files modified:** `src/totem/devices/network/network.py`, `src/totem/hardware/builtin/radio/network.py`.
- **Verification:** Bluetooth, BlueZ, L2CAP, GATT, and existing Wi-Fi compatibility/import-boundary suites passed.
- **Committed in:** `22bacae`.

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking issues).
**Impact on plan:** Both repairs are required for independent catalog discovery and deterministic compatibility regression coverage; neither introduces cross-provider ownership.

## Issues Encountered

- The broader `tests/unit/test_driver_contracts.py` suite still has pre-existing legacy `DeviceDriver` inheritance failures beginning with the display facade; this task did not alter or defer that unrelated migration window.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Later hardware migration plans can compose BlueZ independently and use the same provider-local manifest convention for distinct built-ins in one package.
- No device, SSH, network, D-Bus service, radio, USB/serial/I2C/GPIO, deployment, or hardware-marked test was contacted.

## Self-Check: PASSED

- Found the Bluetooth provider, manifest, relocated canonical implementations, test suite, and summary on disk.
- Found TDD commits `36554f6` and `22bacae` in git history.
