---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: Capability-Oriented Hardware Runtime
status: executing
stopped_at: Completed HW-01-02-PLAN.md
last_updated: "2026-08-23T19:33:29.770Z"
last_activity: 2026-08-22
last_activity_desc: Phase 1 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 33
  completed_plans: 2
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-22)

**Core value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.
**Current focus:** Phase 1 — Capability-Oriented Hardware Runtime

## Current Position

Phase: 1 (Capability-Oriented Hardware Runtime) — EXECUTING
Plan: 3 of 33
Status: Ready to execute
Last activity: 2026-08-22 — Phase 1 execution started

Progress: ░░░░░░░░░░ [█░░░░░░░░░] 6%

## Accumulated Context

### Decisions

- Capabilities, not device subclasses, form the stable extension boundary.
- Third-party drivers are independently installable Python distributions.
- Process isolation is the default; in-process execution is explicit opt-in.
- Both host modes share one transport-neutral contract.
- That contract follows NIP-5D's typed message and correlated-result pattern,
  matching the vocabulary already used by `totemd`.

- PR #22 commit `211f890b` is the implementation baseline.
- [Phase HW-01]: Use .venv/bin/python for all later local Python and pytest claims.
- [Phase HW-01]: Synthetic benchmark evidence is local-only and cannot claim Pi acceptance.
- [Phase HW-01]: Public driver API is stdlib-only and supports Python 3.9 or newer.
- [Phase HW-01]: Driver manifests are package data inspected before an entry point can import provider code.
- [Phase HW-01]: Public messages copy strict JSON values into immutable containers before concurrent reuse.

### Roadmap Evolution

- Phase 1 added: Capability-Oriented Hardware Runtime

### Pending Todos

None yet.

### Blockers/Concerns

- IPC encoding and driver-process granularity need measurement on Pi-class
  hardware before the runtime contract is frozen.

## Session Continuity

Last session: 2026-08-23T19:33:29.763Z
Stopped at: Completed HW-01-02-PLAN.md
Resume file: None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase HW-01 P01 | 4m | 1 tasks | 8 files |
| Phase HW-01-capability-oriented-hardware-runtime P02 | 5m | 1 tasks | 14 files |
