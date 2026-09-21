---
phase: HW-01-capability-oriented-hardware-runtime
plan: "05"
subsystem: hardware-runtime
tags: [python, manifests, configuration, toml, diagnostics, security]
requires:
  - phase: HW-01-04
    provides: Import-free catalog and claimed-binding tracer
provides:
  - Versioned immutable provider manifests with strict schema validation
  - Typed binary-mode TOML startup snapshots with binding precedence
  - Redacted diagnostics and secret reference descriptors
affects: [catalog, discovery, resource-broker, driver-hosts]
tech-stack:
  added: []
  patterns: [manifest-before-import, immutable startup snapshots, binary TOML seam, reference-only secrets]
key-files:
  created:
    - src/totem/hardware/catalog/diagnostics.py
    - src/totem/hardware/runtime/config.py
    - tests/unit/hardware_runtime/test_manifest.py
  modified:
    - packages/totem-driver-api/src/totem_driver_api/manifest.py
    - packages/totem-driver-api/src/totem_driver_api/resources.py
    - packages/totem-driver-api/src/totem_driver_api/__init__.py
    - src/totem/hardware/catalog/manifests.py
    - src/totem/hardware/catalog/metadata.py
    - tests/unit/hardware_runtime/test_catalog.py
    - tests/unit/hardware_runtime/test_config.py
decisions:
  - "Manifest schema is versioned and strict, yet legacy fixture manifests retain safe defaults while new fields are fully validated."
  - "Startup configuration is read through one binary TOML seam and resolved binding > plugin > global > manifest into immutable values."
  - "Secret-bearing settings accept only credential, file, or inherited-descriptor references; values cannot enter manifests or diagnostics."
metrics:
  duration: 5m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 05: Versioned Manifest and Typed Config Summary

**Driver metadata and startup settings now form one immutable, import-free, redacted selection input before resolution, claims, or provider startup.**

## Accomplishments

- Expanded `DriverManifest` with manifest/API/capability versions, predicates, prerequisites, config schema/defaults, resource grouping, privileges, grouping policy, and factory metadata.
- Added strict unknown-field and incompatible-major rejection with structured `CatalogDiagnostic` evidence that identifies only safe plugin/binding/field metadata.
- Added immutable `RuntimeConfig`, plugin/binding sections, descriptor-only secret references, and exact binding → plugin → global → manifest precedence.
- Added binary-mode TOML parsing through the Python-version seam (`tomli` for 3.9/3.10 and `tomllib` from 3.11), while retaining direct config injection for local tests.
- Proved schema, precedence, invalid-sibling isolation, concurrent readers, secret redaction, and manifest-before-import behavior with local fixtures only.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog.py tests/unit/hardware_runtime/test_config.py -x` — passed (11 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_config.py -k 'concurrent or secret' -x` — passed (3 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_manifest.py -k schema -x` — passed (1 test).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (166 tests).
- `.venv/bin/python -m compileall -q packages/totem-driver-api/src/totem_driver_api src/totem/hardware/catalog src/totem/hardware/runtime tests/unit/hardware_runtime/test_catalog.py tests/unit/hardware_runtime/test_config.py tests/unit/hardware_runtime/test_manifest.py` — passed.
- Scoped Flake8 could not run because it is not installed in `.venv`; it is not a plan verification command.

## TDD Gate Compliance

- RED `1a1021c` added the behavior tests; the focused suite failed at collection because `manifest_from_document` did not yet exist.
- GREEN `48443c8` implemented the strict manifest/config boundary; focused, probe-ledger, and full local unit suites pass.

## Task Commits

1. **Task 1 RED: Specify versioned manifest and startup-config validation** — `1a1021c` (`test`)
2. **Task 1 GREEN: Complete immutable manifest and typed startup-config validation** — `48443c8` (`feat`)

## Decisions Made

- Manifest version incompatibility, API incompatibility, and unknown metadata are diagnosed before catalog records can reach resolution or resource claims.
- Config diagnostics identify the plugin, binding, field, and stable code while excluding input values and secret references.
- Reference-only credentials are valid only at runtime configuration; manifests never carry secret defaults.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical verification] Added the probe-ledger manifest schema test.**
- **Found during:** Task 1 acceptance audit.
- **Issue:** The source-audit/probe-ledger contract names `tests/unit/hardware_runtime/test_manifest.py -k schema`, but the plan's narrower test-file list did not create that executable verifier.
- **Fix:** Added a local schema-level test that asserts every required version, selection, resource, privilege, grouping, and factory declaration without importing a provider.
- **Files modified:** `tests/unit/hardware_runtime/test_manifest.py`.
- **Commit:** `48443c8`.

**Total deviations:** 1 auto-fixed Rule 2 verification addition. **Impact:** Satisfies the named source-audit contract with no hardware, network, or provider execution.

## Known Stubs

None.

## Threat Flags

None — this plan only deepens the already planned manifest/config trust boundary; it adds no endpoint, file-access path, or schema boundary beyond strict local startup parsing.

## Next Phase Readiness

The catalog now yields complete immutable metadata and typed effective settings ready for pure resolution and resource expansion. The existing `tomli>=2.0,<3.0; python_version < '3.11'` project dependency already matched the plan, so no dependency mutation was needed. No hardware-marked tests, SSH, device access, deployment, or physical resource contact occurred.

## Self-Check: PASSED

- All created catalog/config/test files exist in the worktree.
- RED and GREEN commits `1a1021c` and `48443c8` exist in git history.
