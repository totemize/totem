---
phase: HW-01-capability-oriented-hardware-runtime
plan: "20"
subsystem: hardware-wifi-provider
tags: [wifi, networkmanager, nan, p2p, radio, dual-host, pytest]
requires:
  - phase: HW-01-19
    provides: Versioned Wi-Fi contracts, radio claim coexistence policy, and injected D-Bus support.
provides:
  - Import-safe built-in Wi-Fi provider manifest and entry point.
  - Lease-gated NetworkManager, mock, P2P, and NAN session ownership.
  - Matching process and in-process Wi-Fi message dispatch using injected mocks.
affects: [HW-01-21, radio-providers, runtime-broker, compatibility-facades]
tech-stack:
  added: []
  patterns:
    - Provider composition validates declared D-Bus service, interface, and PHY claims before importing or invoking a driver.
    - Radio provider actions use the shared host dispatch contract without constructing another radio provider.
key-files:
  created:
    - src/totem/hardware/builtin/radio/wifi_provider.py
    - src/totem/hardware/builtin/radio/wifi-manifest.json
    - src/totem/hardware/builtin/radio/totem-driver-manifest.json
    - src/totem/hardware/builtin/radio/nan.py
    - src/totem/hardware/builtin/radio/drivers/network_manager_wifi.py
    - tests/unit/hardware_runtime/test_builtin_wifi.py
  modified:
    - pyproject.toml
    - src/totem/hardware/hosts/in_process.py
    - src/totem/hardware/hosts/worker.py
    - tests/unit/test_radio_primitives.py
key-decisions:
  - "Wi-Fi validates leased NetworkManager service, interface, and PHY facts before driver composition; caller payloads never select identities."
  - "The existing catalog filename remains authoritative, so the requested Wi-Fi declaration is accompanied by a package-discoverable totem-driver-manifest.json copy."
patterns-established:
  - "Provider-local restart and quarantine state can rebuild only a selected Wi-Fi session while shared-PHY admission remains broker policy."
requirements-completed: [API-02, RUN-03, TST-04]
coverage:
  - id: D1
    description: Built-in Wi-Fi is cataloged without importing the NetworkManager provider and validates exact broker claims before session creation.
    requirement: API-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_wifi.py#test_catalog_reads_wifi_manifest_without_importing_network_manager_provider
        status: pass
    human_judgment: false
  - id: D2
    description: Mock Wi-Fi retains station, AP, P2P, and NAN primitives through matching process and in-process host transcripts.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_wifi.py#test_wifi_has_matching_dual_host_contract_using_mock_session_only
        status: pass
    human_judgment: false
  - id: D3
    description: Wi-Fi restart is provider-local and shared-PHY conflicts reject before provider activity.
    requirement: RUN-03
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_wifi.py#test_wifi_failure_restart_and_shared_phy_denial_are_provider_local
        status: pass
    human_judgment: false
duration: 13min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 20: Independent Wi-Fi Provider Summary

**NetworkManager Wi-Fi is now an import-safe, lease-gated provider with preserved mock, station, AP, P2P, and NAN primitives under both host modes.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-26T14:21:30Z
- **Completed:** 2026-08-26T14:34:36Z
- **Tasks:** 1/1
- **Files modified:** 16

## Accomplishments

- Published a package-data Wi-Fi declaration, catalog entry point, and side-effect-free provider factory.
- Relocated the NetworkManager, mock, onboard, USB, and NAN Wi-Fi implementations under built-in radio ownership.
- Preserved deterministic station, hotspot, P2P, and Aware behavior and added local-only dual-host conformance coverage.
- Added worker and in-process dispatch for the versioned Wi-Fi contracts, with service/interface/PHY validation before driver work.

## Task Commits

1. **Task 1: Implement the independent Wi-Fi provider and sessions (RED)** — `00c3d38` (`test`)
2. **Task 1: Implement the independent Wi-Fi provider and sessions (GREEN)** — `a5ea324` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_wifi.py tests/unit/test_radio_primitives.py -k 'wifi or nan' -x` — 12 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_in_process_host.py tests/unit/hardware_runtime/test_radio_resources.py tests/unit/hardware_runtime/test_radio_shared_support.py -x` — 23 passed.
- `.venv/bin/python -m compileall -q src/totem/hardware/builtin/radio src/totem/hardware/hosts` and `git diff --check` — passed.
- `black --check` was unavailable in `.venv`; it was not a plan verification gate.

## Files Created/Modified

- `src/totem/hardware/builtin/radio/wifi_provider.py` — Validates leased facts, manages one Wi-Fi session's local lifecycle, and maps session actions to public contracts.
- `src/totem/hardware/builtin/radio/{wifi-manifest.json,totem-driver-manifest.json}` — Data-only Wi-Fi provider declarations, including catalog-compatible package metadata.
- `src/totem/hardware/builtin/radio/{nan.py,drivers/}` — Canonical NetworkManager, mock, onboard, USB, and NAN behavior.
- `src/totem/hardware/hosts/{in_process.py,worker.py}` — Matching Wi-Fi logical dispatch for both host implementations.
- `tests/unit/hardware_runtime/test_builtin_wifi.py` — Import boundary, claim validation, session, lifecycle, coexistence, and dual-host fixture tests.

## Decisions Made

- Validate the D-Bus service, interface, and PHY claims against the selected session facts before any concrete driver import or backend call.
- Keep shared-PHY admission in Plan 19's broker policy; the Wi-Fi provider owns only its own session lifecycle.
- Keep the requested `wifi-manifest.json` and add the catalog's established manifest filename instead of changing package discovery behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added the catalog-required manifest filename**
- **Found during:** Task 1 GREEN verification.
- **Issue:** The existing `CatalogScanner` only reads package files named `totem-driver-manifest.json`; its required filename differs from the plan's requested `wifi-manifest.json`.
- **Fix:** Preserved `wifi-manifest.json` and added an identical catalog-compatible `totem-driver-manifest.json` package-data declaration.
- **Files modified:** `src/totem/hardware/builtin/radio/totem-driver-manifest.json`, `pyproject.toml`, `tests/unit/hardware_runtime/test_builtin_wifi.py`.
- **Verification:** Import-free catalog test passed.
- **Committed in:** `a5ea324`.

**2. [Rule 2 - Missing Critical] Extended the common host dispatcher for Wi-Fi contracts**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** Process and in-process hosts could not execute the newly declared Wi-Fi contract, so dual-host conformance would have diverged.
- **Fix:** Added narrow scan/connect/disconnect/hotspot dispatch and forwarding with public value validation.
- **Files modified:** `src/totem/hardware/hosts/worker.py`, `src/totem/hardware/hosts/in_process.py`, `src/totem/hardware/builtin/radio/wifi_provider.py`.
- **Verification:** Dual-host Wi-Fi transcript and existing host suites passed.
- **Committed in:** `a5ea324`.

---

**Total deviations:** 2 auto-fixed (1 Rule 2 missing critical, 1 Rule 3 blocking).
**Impact on plan:** Both changes are required to make the requested provider discoverable and behaviorally identical under the established host contract.

## Issues Encountered

- The local virtual environment does not install Black, so its optional formatting check could not run; focused tests, compile checks, and whitespace validation succeeded.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 21 can add the Bluetooth provider against the shared radio policy and established dual-host dispatch seam.
- No device, SSH, network, D-Bus service, radio, USB/serial/I2C/GPIO, deployment, or hardware-marked test was contacted.

## Self-Check: PASSED

- Found every declared provider, manifest, relocated session, and focused test file on disk.
- Found TDD commits `00c3d38` and `a5ea324` in git history.
