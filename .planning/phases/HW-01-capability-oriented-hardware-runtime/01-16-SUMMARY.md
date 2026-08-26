---
phase: HW-01-capability-oriented-hardware-runtime
plan: "16"
subsystem: hardware-power-provider
tags: [power, telemetry, i2c, capability, process-host, compatibility-facade, pytest]
requires:
  - phase: HW-01-10
    provides: Matching process and in-process driver-host conformance boundary.
  - phase: HW-01-14
    provides: Exact legacy facade identity and AST source-audit pattern.
provides:
  - Versioned power.telemetry@1 public request, snapshot, and typed push contracts.
  - Import-free built-in power manifest with explicit profile evidence and I2C lease declaration.
  - Canonical PiSugar2 and Waveshare UPS HAT (C) providers with legacy re-export facades.
affects: [HW-01-28, HW-01-29, legacy-contracts, power-facade]
tech-stack:
  added: []
  patterns:
    - Provider families expose strict public telemetry values after selection, evidence, and lease validation.
    - Legacy UPS driver modules retain exact canonical identity while owning no I2C, registry, or runtime logic.
key-files:
  created:
    - packages/totem-driver-api/src/totem_driver_api/capabilities/power.py
    - src/totem/hardware/builtin/power/provider.py
    - src/totem/hardware/builtin/power/totem-driver-manifest.json
    - tests/unit/hardware_runtime/test_builtin_power.py
  modified:
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/hosts/in_process.py
    - src/totem/devices/ups/drivers/pisugar2.py
    - src/totem/devices/ups/drivers/waveshare_ups_hat_c.py
key-decisions:
  - "The canonical provider requires a selected model, matching I2C address evidence, and an acquired I2C bus claim before calling its injected driver."
  - "Canonical UPS drivers preserve status attributes and mock transport semantics without inheriting the legacy DeviceDriver hierarchy."
patterns-established:
  - "When a new capability has both host modes, worker dispatch and the in-process cancellation proxy must expose the same typed operations."
requirements-completed: [HWR-02, SPI-06, TST-04]
coverage:
  - id: D1
    description: PiSugar2 and Waveshare UPS HAT (C) telemetry is available as validated power.telemetry@1 snapshots and typed pushes under both host modes.
    requirement: HWR-02
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_power.py#test_power_provider_has_matching_dual_host_snapshot_and_push_conformance
        status: pass
    human_judgment: false
  - id: D2
    description: Catalog resolution needs data-only profile evidence and the I2C lease before the power provider can access an injected transport.
    requirement: SPI-06
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_power.py#test_profiled_i2c_evidence_resolves_and_claims_before_provider_access
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_power.py#test_provider_rejects_missing_claims_or_unknown_hat_before_i2c_access
        status: pass
    human_judgment: false
  - id: D3
    description: Historical UPS driver imports preserve canonical object identity while containing no legacy I2C, registry, or runtime owner code.
    requirement: TST-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_builtin_power.py#test_legacy_ups_sources_have_no_registry_or_runtime_ownership
        status: pass
      - kind: unit
        ref: .venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py -x
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 16: Built-in Power Telemetry Summary

**PiSugar2 and Waveshare UPS HAT (C) telemetry now runs as an import-free, lease-gated `power.telemetry@1` provider with exact legacy import facades.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-26T12:54:43Z
- **Completed:** 2026-08-26T13:06:15Z
- **Tasks:** 1/1
- **Files modified:** 15

## Accomplishments

- Added strict public power telemetry request, snapshot, and typed push contracts, including finite numeric and charging-state validation.
- Registered the canonical built-in provider through a package-data manifest that requires profile evidence and an exclusive I2C bus lease before child composition.
- Moved PiSugar2 and Waveshare I2C implementations to `totem.hardware.builtin.power`; historical UPS paths now directly re-export the exact canonical classes.
- Extended the shared worker and in-process host seam so snapshot and push messages have matching functional transcripts.

## Task Commits

1. **Task 1: Catalog both UPS implementations behind power telemetry (RED)** — `4da9a19` (`test`)
2. **Task 1: Catalog both UPS implementations behind power telemetry (GREEN)** — `37ee075` (`feat`)

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/capabilities/power.py` — Versioned public power telemetry models.
- `src/totem/hardware/builtin/power/` — Cataloged provider, manifest, and relocated injected-I2C drivers.
- `src/totem/hardware/hosts/worker.py` and `src/totem/hardware/hosts/in_process.py` — Host-parity dispatch for power snapshot and push messages.
- `src/totem/devices/ups/drivers/` — Thin canonical re-exports with no driver, registry, or transport ownership.
- `tests/unit/hardware_runtime/test_builtin_power.py` — Manifest/import-boundary, evidence/claim, dual-host, and facade source audits.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_power.py tests/unit/test_pisugar2.py tests/unit/test_waveshare_ups_hat_c.py tests/unit/hardware_runtime/test_import_boundaries.py -x` — 24 passed.
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — 133 passed.
- `compileall`, `git diff --check`, and direct source audits for facade ownership and canonical legacy imports — passed.
- Full `tests/unit` run: 267 passed and 29 known migration-window failures. The existing display facade/registry failures remain out of scope; the two new UPS inheritance assertions are recorded in Windows entry 12 for Plan 01-28.

## Decisions Made

- Require an explicit selected UPS model and its matching data-only I2C address before an injected driver can read telemetry; a bus claim alone cannot identify a HAT.
- Preserve legacy status attributes and mock transport behavior without retaining `DeviceDriver` inheritance in canonical ownership.
- Use an explicit typed `power.telemetry.push` value instead of exposing raw provider or configuration details.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Complete the shared host dispatch seam for power operations**
- **Found during:** Task 1 (dual-host conformance)
- **Issue:** The worker and in-process cancellation proxy forwarded only display frames, so an otherwise valid in-process power request became `invalid_request`.
- **Fix:** Added validated `power.telemetry.read` and `power.telemetry.push` dispatch plus corresponding in-process proxy methods.
- **Files modified:** `src/totem/hardware/hosts/worker.py`, `src/totem/hardware/hosts/in_process.py`
- **Verification:** Process and in-process conformance transcripts now match using mock-only providers.
- **Committed in:** `37ee075` (part of Task 1 GREEN)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The fix is required for the planned two-host power capability and introduces no new trust boundary beyond the plan's declared provider-to-host boundary.

## Issues Encountered

- `tests/unit/test_driver_contracts.py -k 'pisugar2 or waveshare_ups_hat_c'` has exactly two expected stale inheritance assertions. Canonical drivers intentionally no longer subclass `DeviceDriver` or `UPSDeviceInterface`; Windows entry 12 assigns their conversion/removal to Plan 01-28.
- The complete unit suite has 29 failures, all in the already-open display compatibility migration window plus the two UPS assertions above. The scoped power and full hardware-runtime suites are green.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-28 can retire the two stale UPS legacy inheritance checks along with the existing display migration assertions.
- Plan 01-29 can replace the remaining legacy `UPS` wrapper/registry ownership with a capability client facade.
- No device, SSH, deployment, network, I2C/GPIO access, hardware-marked test, or physical resource contact occurred.

## Self-Check: PASSED

- The public contract, canonical provider/manifest, driver facades, focused test, and this summary exist.
- TDD commits `4da9a19` and `37ee075` exist on `refactor/hardware-ontology`.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
