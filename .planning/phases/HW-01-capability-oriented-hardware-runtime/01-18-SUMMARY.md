---
phase: HW-01-capability-oriented-hardware-runtime
plan: "18"
subsystem: hardware-storage-provider
tags: [storage, filesystem, nvme, capability, resource-lease, process-host, compatibility-facade, pytest]
requires:
  - phase: HW-01-10
    provides: Matching process and in-process driver-host conformance boundary.
  - phase: HW-01-17
    provides: Import-free built-in provider and compatibility-facade pattern.
provides:
  - Versioned storage.files@1 bounded read, write, list, and delete values.
  - Import-free built-in storage manifest with exclusive root, mount, and block claims.
  - Canonical filesystem and NVMe implementations plus historical storage re-export facades.
affects: [HW-01-28, HW-01-29, storage-facade, hardware-runtime]
tech-stack:
  added: []
  patterns:
    - Public file requests normalize relative POSIX paths and bound binary values before child dispatch.
    - A storage provider validates leased resource identity and real-root confinement before it calls an injected driver.
key-files:
  created:
    - packages/totem-driver-api/src/totem_driver_api/capabilities/storage.py
    - src/totem/hardware/builtin/storage/provider.py
    - src/totem/hardware/builtin/storage/totem-driver-manifest.json
    - tests/unit/hardware_runtime/test_builtin_storage.py
  modified:
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/hosts/in_process.py
    - src/totem/devices/storage/device.py
    - src/totem/devices/storage/files.py
key-decisions:
  - "Use storage.files@1 base64 values capped at 4096 bytes and normalized relative POSIX paths so invalid paths and oversized payloads never reach a provider driver."
  - "Require explicit exclusive root, mount, and block claims before storage initialization; the configured root itself is injected only after selection."
patterns-established:
  - "When a capability shares method names with another provider, the in-process cancellation proxy must forward its selected operation arguments generically and retain dual-host regression coverage."
requirements-completed: [HWR-02, SPI-06, TST-04]
coverage:
  - id: D1
    description: Filesystem and NVMe implementations expose storage.files@1 read, write, list, and delete requests with matching process/in-process transcripts.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_storage.py#test_storage_provider_has_matching_dual_host_read_write_list_delete_conformance
        status: pass
    human_judgment: false
  - id: D2
    description: The import-free storage manifest resolves only after root, mount, and block facts are present, and exclusive claims identify conflicting owners.
    requirement: SPI-06
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_storage.py#test_storage_facts_resolve_all_root_mount_and_block_claims_before_provider_import
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_storage.py#test_exclusive_root_claim_conflict_identifies_both_binding_owners
        status: pass
    human_judgment: false
  - id: D3
    description: Traversal, absolute paths, and symlink escapes are rejected before storage driver file I/O while historical imports retain canonical identity.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_storage.py#test_provider_rejects_path_escapes_before_driver_file_access
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_storage.py tests/unit/test_storage.py -x
        status: pass
    human_judgment: false
duration: 40min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 18: Built-in Storage Provider Summary

**Filesystem and NVMe storage now run through a bounded, root-confined `storage.files@1` provider with exclusive resource claims, both-host parity, and exact legacy import facades.**

## Performance

- **Duration:** 40 min
- **Tasks:** 1/1
- **Files modified:** 16

## Accomplishments

- Added strict public storage messages: normalized relative POSIX paths, JSON-safe bounded binary reads/writes, deterministic listings, and explicit delete results.
- Registered the built-in storage provider through package data that demands exact root, mount, and block facts and grants exclusive claims before provider initialization.
- Moved filesystem and generic NVMe implementations beneath `totem.hardware.builtin.storage`, then converted historical storage files and drivers into canonical re-exports.
- Extended worker and in-process host dispatch so storage operations share the same process/in-process logical transcript using temporary local roots only.

## Task Commits

1. **Task 1: Catalog filesystem and NVMe storage with scoped path claims (RED)** — `1698b32` (`test`)
2. **Task 1: Catalog filesystem and NVMe storage with scoped path claims (GREEN)** — `40971e8` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_storage.py tests/unit/test_storage.py -x` — 25 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_storage.py tests/unit/test_storage.py tests/unit/hardware_runtime/test_builtin_nfc.py tests/unit/hardware_runtime/test_builtin_power.py tests/unit/hardware_runtime/test_conformance.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 51 passed.
- `compileall` for the public contract, storage provider, and host dispatchers — passed.
- `git diff --check` and legacy facade AST/source audits — passed.

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/capabilities/storage.py` — Versioned, bounded storage request/result values.
- `src/totem/hardware/builtin/storage/` — Import-free manifest, root confinement, provider, and canonical filesystem/NVMe drivers.
- `src/totem/hardware/hosts/worker.py` and `src/totem/hardware/hosts/in_process.py` — Matching storage request dispatch for both hosts.
- `src/totem/devices/storage/` — Compatibility re-exports and structural driver validation for canonical classes.
- `tests/unit/hardware_runtime/test_builtin_storage.py` — Catalog, facts, lease conflict, path safety, both-host, and facade tests using temporary roots.

## Decisions Made

- Storage transport messages carry only normalized relative paths and bounded base64 data; no absolute host path or file contents can enter diagnostics.
- A provider must hold exclusive root, mount, and block claims before initializing its injected driver, while the concrete filesystem root stays child-composed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Complete shared host and legacy compatibility seams**
- **Found during:** Task 1 (dual-host provider conformance)
- **Issue:** The generic worker/in-process host lacked storage dispatch, and legacy `Storage` required canonical drivers to inherit a legacy base class, which would invert the ownership boundary.
- **Fix:** Added matching storage read/write/list/delete dispatch and changed the legacy loader to validate the required driver protocol structurally.
- **Files modified:** `src/totem/hardware/hosts/worker.py`, `src/totem/hardware/hosts/in_process.py`, `src/totem/devices/storage/device.py`
- **Verification:** 51 focused storage, NFC, power, conformance, and import-boundary tests passed.
- **Committed in:** `40971e8` (part of Task 1 GREEN)

**2. [Rule 1 - Bug] Preserve NFC dispatch while adding storage method forwarding**
- **Found during:** Task 1 (runtime regression verification)
- **Issue:** Initial storage-specific cancellation-proxy methods shadowed the existing NFC `read` and `write` forwarding methods, causing in-process NFC conformance to return `invalid_request`.
- **Fix:** Made the shared proxy forward `read` and `write` argument lists generically; retained storage-only list/delete forwarding separately.
- **Files modified:** `src/totem/hardware/hosts/in_process.py`
- **Verification:** NFC, power, storage, conformance, and import-boundary regression group passed (51 tests).
- **Committed in:** `40971e8` (part of Task 1 GREEN)

---

**Total deviations:** 2 auto-fixed (1 Rule 2 missing critical functionality, 1 Rule 1 bug).
**Impact on plan:** Both fixes are necessary for a working shared host contract and canonical ownership; they add no new hardware or network surface.

## Issues Encountered

None.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Storage now follows the provider and compatibility-facade pattern required by Plan 01-28.
- No device, SSH, deployment, network, USB/serial/I2C/GPIO access, hardware-marked test, or physical resource contact occurred.

## Self-Check: PASSED

- Found the public contract, canonical provider/manifest, relocated drivers, compatibility facades, focused test, and this summary on disk.
- Found TDD commits `1698b32` and `40971e8` in git history.
