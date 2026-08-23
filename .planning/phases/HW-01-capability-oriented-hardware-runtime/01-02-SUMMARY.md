---
phase: HW-01-capability-oriented-hardware-runtime
plan: "02"
subsystem: packaging
tags: [python, setuptools, driver-api, plugin-fixture, immutable-contracts]
requires:
  - phase: HW-01-01
    provides: Controlled Python 3.9 test environment and hardware-free test baseline
provides:
  - Independently buildable public `totem-driver-api` wheel
  - Independently buildable fixture provider wheel with import-free manifest
  - Immutable public capability, message, manifest, and resource value contracts
affects: [catalog, resolver, driver-hosts, capability-runtime]
tech-stack:
  added: [setuptools package metadata]
  patterns: [import-free manifest inspection, frozen strict-JSON public values, package-data fixture manifests]
key-files:
  created:
    - packages/totem-driver-api/pyproject.toml
    - packages/totem-driver-api/src/totem_driver_api/manifest.py
    - tests/fixtures/totem-driver-fixture/pyproject.toml
    - tests/unit/hardware_runtime/test_public_api_fixture.py
  modified:
    - pyproject.toml
key-decisions:
  - "The public driver API is stdlib-only and supports Python 3.9 or newer."
  - "Driver manifests are package data inspected before an entry point can import provider code."
  - "Public messages copy strict JSON values into immutable containers before concurrent reuse."
patterns-established:
  - "Catalog code locates a distribution manifest through package data rather than loading its entry point."
  - "Capability IDs use independent `name@major` compatibility versioning while the API major gates a provider distribution."
requirements-completed: [HWR-02, SPI-02]
coverage:
  - id: D1
    description: Public Python 3.9 driver API wheel with immutable capability, manifest, resource, and message contracts
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_public_api_fixture.py#test_public_api_is_import_independent_and_python_39_compatible
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit -x -q --tb=short
        status: pass
    human_judgment: false
  - id: D2
    description: Independently installable fixture provider wheel with package-data manifest, entry point, and import sentinel
    requirement: SPI-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_public_api_fixture.py#test_wheels_install_separately_include_manifest_and_register_entry_point
        status: pass
    human_judgment: false
duration: 5min
completed: 2026-08-23
status: complete
---

# Phase HW-01 Plan 02: Public Driver API Fixture Summary

**Python 3.9 public driver contracts and an independently installable display fixture wheel that can be cataloged without importing provider code**

## Performance

- **Duration:** 5 min
- **Started:** 2026-08-23T19:27:25Z
- **Completed:** 2026-08-23T19:32:18Z
- **Tasks:** 1
- **Files modified:** 14

## Accomplishments

- Published a stdlib-only `totem-driver-api` package with versioned capability IDs, immutable manifests/resources/messages, and the `display.frame-sink@1` contract.
- Added a separate fixture distribution with package-data manifest, `totem.hardware.drivers` entry point, and an import sentinel that remains clear throughout manifest/API-major validation.
- Proved both wheels build and install under the controlled Python 3.9 environment, then completed the full local unit suite without hardware contact.

## Task Commits

1. **Task 1: Publish the public API and independently installable fixture wheel** — `3801657` (test), `55afec3` (feat)

## Files Created/Modified

- `packages/totem-driver-api/` — public, dependency-free API distribution and display capability contract.
- `tests/fixtures/totem-driver-fixture/` — independently packaged synthetic display provider and import-free manifest.
- `tests/unit/hardware_runtime/test_public_api_fixture.py` — wheel, package-data, entry-point, dependency-direction, immutability, concurrency, and API-major proof.
- `pyproject.toml` — declares the local public API as a Poetry development dependency while retaining Wave-0's Linux production marker and unconditional dev/test `dbus-next` seam.

## Decisions Made

- Used `setuptools` PEP 517 metadata for the standalone API and fixture packages so each can build as a wheel without Totem-core packaging.
- Kept provider code out of the fixture package initializer; catalog consumers can inspect the installed manifest and reject API incompatibility before any entry point is loaded.
- Froze nested logical-message JSON data on construction to make public values safe to share across simultaneous callers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test helper] Selected the correct wheel when both packages build into one directory**
- **Found during:** Task 1
- **Issue:** The initial test helper selected the first wheel in the shared wheel directory, which could inspect the API wheel while asserting fixture contents.
- **Fix:** Selected the built wheel by normalized distribution name.
- **Files modified:** `tests/unit/hardware_runtime/test_public_api_fixture.py`
- **Verification:** Focused wheel/package-data test passed.
- **Committed in:** `55afec3`

**2. [Rule 1 - Test helper] Located nested package data through distribution files**
- **Found during:** Task 1
- **Issue:** `importlib.metadata.Distribution.read_text()` does not address nested package-data paths.
- **Fix:** Resolved the manifest from the distribution file list and read it through `locate_file()` without importing the provider.
- **Files modified:** `tests/unit/hardware_runtime/test_public_api_fixture.py`
- **Verification:** The controlled independent-install test passed with the sentinel unset.
- **Committed in:** `55afec3`

**3. [Rule 2 - Correctness] Deep-froze logical-message JSON values**
- **Found during:** Task 1
- **Issue:** A frozen dataclass still retained caller-owned nested mappings, allowing mutation after construction and violating concurrent reuse guarantees.
- **Fix:** Copy strict JSON values into private immutable arrays/objects and return fresh standard JSON values.
- **Files modified:** `packages/totem-driver-api/src/totem_driver_api/messages.py`, `tests/unit/hardware_runtime/test_public_api_fixture.py`
- **Verification:** Immutability/concurrent-reuse test and full unit suite passed.
- **Committed in:** `55afec3`

**4. [Rule 2 - Project convention] Recorded the session in the required dated journal**
- **Found during:** Plan close-out
- **Issue:** `AGENTS.md` requires each closed session to append the dated journal and its index.
- **Fix:** Added the no-device packaging result to the 2026-08-23 journal and index.
- **Files modified:** `.journey/journal/2026-08-23.md`, `.journey/README.md`
- **Verification:** Journal entry and index link exist.
- **Committed in:** Plan metadata commit

---

**Total deviations:** 4 auto-fixed (2 test-helper bugs, 1 public-contract immutability correction, 1 required project record).
**Impact on plan:** All corrections directly enforce the planned import-boundary and concurrent immutability guarantees.

## Issues Encountered

None remaining.

## Known Stubs

None.

## Next Phase Readiness

Plan 03 can locate and validate the fixture wheel's package-data manifest, check its API major, resolve `display.frame-sink@1`, and claim its synthetic SPI resource before importing provider code. Pi acceptance and all device access remain explicitly deferred.

## Self-Check: PASSED

- Public API, fixture distribution, manifest, focused test, and summary files exist in the worktree.
- RED and GREEN commits `3801657` and `55afec3` exist in git history.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-23*
