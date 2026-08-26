---
phase: HW-01-capability-oriented-hardware-runtime
plan: "06"
subsystem: hardware-discovery
tags: [python, hardware-facts, profiles, resolver, binding-plan, deterministic]
requires:
  - phase: HW-01
    provides: import-free catalog metadata and typed runtime configuration
provides:
  - Immutable normalized hardware components, facts, inventory, and data-only profiles
  - Complete deterministic match evidence and fail-closed binding plans
affects: [resource-broker, runtime-lifecycle, builtin-providers]
tech-stack:
  added: []
  patterns: [immutable evidence snapshots, data-only profile evidence, deterministic resolver ranking]
key-files:
  created: [src/totem/hardware/discovery/inventory.py, src/totem/hardware/discovery/profiles.py, tests/unit/hardware_runtime/test_resolver.py]
  modified: [src/totem/hardware/discovery/facts.py, src/totem/hardware/discovery/resolver.py, src/totem/hardware/runtime/bindings.py]
key-decisions:
  - "Observed predicate evidence scores above supplemental profile evidence; profiles cannot satisfy resources or service prerequisites."
  - "A configured binding selects its provider only after capability, configuration, prerequisite, and resource checks pass."
patterns-established:
  - "Resolution records every accepted and rejected candidate in lexically ordered, serializable evidence."
  - "Equal highest automatic matches are ambiguous and never selected arbitrarily."
requirements-completed: [HWR-01, CMP-01, CMP-02, CMP-03, CMP-04, TST-02]
coverage:
  - id: D1
    description: Immutable normalized hardware facts and data-only profiles cover platform, bus, device-tree, adapter, and service fixture evidence.
    requirement: HWR-01
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_resolver.py
        status: pass
    human_judgment: false
  - id: D2
    description: Resolver produces complete, deterministic candidate evidence, honors safe explicit bindings, and fails closed on tied automatic matches.
    requirement: CMP-01
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_resolver.py
        status: pass
    human_judgment: false
duration: 8min
completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 06: Evidence-Bearing Hardware Resolver Summary

**Immutable hardware facts and data-only profiles now produce deterministic, complete binding evidence before any provider initialization.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-26T11:24:00Z
- **Completed:** 2026-08-26T11:32:35Z
- **Tasks:** 1/1
- **Files modified:** 8

## Accomplishments

- Added immutable normalized hardware components/facts for platform, bus, device-tree, USB, interface, PHY, adapter, OS/kernel, and service evidence.
- Added inventory and data-only profile seams with no provider loading or device-model selection.
- Added complete candidate `MatchResult` evidence and serializable `BindingPlan` output; automatic ties fail closed.
- Enforced that explicit binding selection cannot bypass capability, config, service-prerequisite, or exact-resource validation.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py -x` — passed (7 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` — passed (72 tests).
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (208 tests).
- Resolver source audit found no concrete-provider import, legacy manager import, or closed product-selection switch.
- `git diff --check` — passed.

## Task Commits

1. **Task 1 RED: Specify immutable discovery evidence** — `ce71b0b` (`test`)
2. **Task 1 GREEN: Resolve fact-based binding plans** — `47fec22` (`feat`)

## Files Created/Modified

- `src/totem/hardware/discovery/facts.py` — immutable normalized component and fact model.
- `src/totem/hardware/discovery/inventory.py` — evidence-only inventory seam.
- `src/totem/hardware/discovery/profiles.py` — constrained data-only profile model.
- `src/totem/hardware/discovery/resolver.py` — deterministic evidence matcher and safe override handling.
- `src/totem/hardware/runtime/bindings.py` — complete pre-host `BindingPlan` representation.
- `tests/unit/hardware_runtime/test_resolver.py` — hardware-free compatibility matrix.

## Decisions Made

- Exact observed predicate evidence outranks supplemental profile evidence; profiles cannot claim resources or required services.
- Explicit config bindings may select a provider over automatic predicates, but never bypass manifest capability, typed config, prerequisite, or resource checks.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Issues Encountered

- The initial complete-evidence assertion omitted the independently satisfied resource and service evidence; the test was corrected to require the full support set.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The resource broker can now consume a complete immutable binding plan without importing a provider. No hardware-marked test, hardware access, SSH, network call, deployment, or device allocation occurred.

## Self-Check: PASSED

- All resolver artifacts and the focused test file exist in the worktree.
- RED and GREEN commits `ce71b0b` and `47fec22` exist in git history.

---
*Phase: HW-01-capability-oriented-hardware-runtime*
*Completed: 2026-08-26*
