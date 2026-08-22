---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: Capability-Oriented Hardware Runtime
status: planning
stopped_at: Phase 1 defined; driver-host spike alignment pending
last_updated: "2026-08-22T15:26:22.996Z"
last_activity: 2026-08-22
last_activity_desc: Added Phase 1 and captured its architecture contract
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 33
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-22)

**Core value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.
**Current focus:** Phase 1 — Capability-Oriented Hardware Runtime

## Current Position

Phase: 1 of 1 (Capability-Oriented Hardware Runtime)
Plan: Not planned
Status: Ready for feasibility spike and phase planning
Last activity: 2026-08-22 — Added Phase 1 and captured its architecture contract

Progress: ░░░░░░░░░░ 0%

## Accumulated Context

### Decisions

- Capabilities, not device subclasses, form the stable extension boundary.
- Third-party drivers are independently installable Python distributions.
- Process isolation is the default; in-process execution is explicit opt-in.
- Both host modes share one transport-neutral contract.
- That contract follows NIP-5D's typed message and correlated-result pattern,
  matching the vocabulary already used by `totemd`.

- PR #22 commit `211f890b` is the implementation baseline.

### Roadmap Evolution

- Phase 1 added: Capability-Oriented Hardware Runtime

### Pending Todos

None yet.

### Blockers/Concerns

- IPC encoding and driver-process granularity need measurement on Pi-class
  hardware before the runtime contract is frozen.

## Session Continuity

Last session: 2026-08-22
Stopped at: Phase 1 defined; driver-host spike alignment pending
Resume file: None
