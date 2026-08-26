---
phase: HW-01-capability-oriented-hardware-runtime
plan: "31"
subsystem: radio compatibility facades
tags: [wifi, bluetooth, compatibility, hardware-client, radio]
requires:
  - phase: HW-01-27
    provides: canonical client radio action translations and client-only manager pattern
  - phase: HW-01-28
    provides: catalog-only legacy registry boundary
provides:
  - Wi-Fi compatibility facade delegated only through the canonical client.
  - Bluetooth compatibility facade delegated only through the canonical client.
  - Fake-client radio facade mapping and ownership regressions.
affects: [HW-01-32, legacy-device-facades, radio-imports]
tech-stack:
  added: []
  patterns:
    - Family wrappers retain signatures and public interface aliases while forwarding only to LegacyHardwareClient.
    - Facade initialization and close are local state transitions; the runtime exclusively owns provider and broker lifecycle.
key-files:
  created:
    - tests/unit/test_device_radio_facades.py
  modified:
    - src/totem/devices/network/network.py
    - src/totem/devices/network/bluetooth.py
key-decisions:
  - "Keep driver names and mock flags as inert compatibility configuration rather than selecting local radio backends."
  - "Route each radio family through distinct Wi-Fi or Bluetooth canonical client operations; shared-PHY admission remains broker policy."
patterns-established:
  - "Radio family facades are injected-client translators with no D-Bus, provider, registry, resource, or coexistence ownership."
requirements-completed: [API-02, API-04, API-05, TST-04]
coverage:
  - id: D1
    description: Wi-Fi compatibility facade maps legacy station, hotspot, P2P, and Aware operations to canonical client calls.
    requirement: API-02
    verification:
      - kind: unit
        ref: tests/unit/test_device_radio_facades.py#test_wifi_preserves_operations_with_an_injected_client_only
        status: pass
    human_judgment: false
  - id: D2
    description: Bluetooth compatibility facade maps legacy radio, BLE/GATT, and L2CAP operations to canonical client calls.
    requirement: API-04
    verification:
      - kind: unit
        ref: tests/unit/test_device_radio_facades.py#test_bluetooth_preserves_operations_with_an_injected_client_only
        status: pass
    human_judgment: false
  - id: D3
    description: Radio facades retain public interface aliases without local backend or coexistence-policy ownership.
    requirement: API-05
    verification:
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/test_device_radio_facades.py tests/unit/test_radio_primitives.py tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
metrics:
  duration: "3m"
  completed: "2026-08-26"
status: complete
---

# Phase HW-01 Plan 31: Radio Family Wrapper Delegation Summary

**Legacy Wi-Fi and Bluetooth family names now preserve their public calls while delegating exclusively to the shared canonical hardware client.**

## Performance

- **Duration:** 3m
- **Started:** 2026-08-26T17:51:00Z
- **Completed:** 2026-08-26T17:54:37Z
- **Tasks:** 1/1
- **Files modified:** 3

## Accomplishments

- Replaced Wi-Fi hardware discovery, driver loading, and direct driver calls with injected `LegacyHardwareClient` delegation for station, AP, P2P, and Aware operations.
- Replaced Bluetooth hardware detection, registry loading, and dynamic driver forwarding with explicit canonical-client delegation for radio state, BLE/GATT, advertisements, and L2CAP.
- Preserved canonical public interface aliases and added injected-fake mapping, local-close, import, and AST ownership coverage.

## Task Commits

1. **Task 1: Delegate radio wrappers to separate Wi-Fi and Bluetooth capabilities (RED)** — `e8943fe` (`test`)
2. **Task 1: Delegate radio wrappers to separate Wi-Fi and Bluetooth capabilities (GREEN)** — `f02dcb5` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_device_radio_facades.py tests/unit/test_radio_primitives.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 41 passed.
- `.venv/bin/python -m compileall -q src/totem/devices/network` — passed.
- `git diff --check` — passed.
- Source audit found no registry, provider, D-Bus, NetworkManager, BlueZ, hardware probe, resource, or coexistence-policy ownership in the radio facades.
- All checks used injected local fakes only; no SSH, network, deployment, live D-Bus/NetworkManager/BlueZ/radio, L2CAP, device, or hardware-marked test was contacted.

## Files Created/Modified

- `src/totem/devices/network/network.py` — Client-only Wi-Fi facade retaining legacy method names and public interface alias.
- `src/totem/devices/network/bluetooth.py` — Client-only Bluetooth facade retaining explicit BLE/GATT/L2CAP method mappings and public interface alias.
- `tests/unit/test_device_radio_facades.py` — Local recording-client delegation, local lifecycle, public alias, and ownership regression tests.

## Decisions Made

- Keep driver names and mock flags as inert outward-boundary configuration; wrappers cannot select a backend or own a provider.
- Map Wi-Fi and Bluetooth calls to separate client action families and leave shared-PHY admission to the broker.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Project continuity] Recorded the required session journal entry**
- **Found during:** Plan close-out.
- **Issue:** `AGENTS.md` requires each completed session to be added to the project journal and index.
- **Fix:** Added the local-only Plan 01-31 result to the dated journal and index.
- **Files modified:** `.journey/journal/2026-08-26.md`, `.journey/README.md`
- **Verification:** Journal entry and index row identify Plan 01-31 and its local-only verification.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 Rule 2 project-continuity requirement).
**Impact on plan:** Documentation-only; radio facade scope remains unchanged.

## Issues Encountered

None.

## Known Stubs

None. The optional `metadata` and `subscription_id` parameters are legacy method inputs, not UI/data placeholders.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wi-Fi and Bluetooth family wrappers can no longer open a local hardware ownership path.
- Plan 01-32 can validate the remaining route, command, environment, and service compatibility surface against client-only radio facades.

## TDD Gate Compliance

- RED `e8943fe` failed as expected because the historical Wi-Fi constructor lacked an injected-client seam.
- GREEN `f02dcb5` replaced local loading/probing with client-only delegation and passed the focused suite.

## Self-Check: PASSED

- Found the declared Wi-Fi, Bluetooth, and radio-facade test files on disk.
- Found TDD commits `e8943fe` and `f02dcb5` in repository history.
