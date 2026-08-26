---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: Capability-Oriented Hardware Runtime
status: executing
stopped_at: Completed HW-01-05-PLAN.md
last_updated: "2026-08-26T11:01:37.203Z"
last_activity: 2026-08-22
last_activity_desc: Phase 1 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 33
  completed_plans: 5
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-22)

**Core value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.
**Current focus:** Phase 1 — Capability-Oriented Hardware Runtime

## Current Position

Phase: 1 (Capability-Oriented Hardware Runtime) — EXECUTING
Plan: 6 of 33
Status: Ready to execute
Last activity: 2026-08-22 — Phase 1 execution started

Progress: ░░░░░░░░░░ [██░░░░░░░░] 15%

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
- [Phase HW-01]: Catalog captures one locked immutable metadata snapshot per controlled runtime start.
- [Phase HW-01]: Resolver matches provider resource declarations only against exact observed facts before issuing a generic binding.
- [Phase HW-01]: Broker normalizes resource identities and atomically grants all binding claims or none.
- [Phase HW-01]: Parent-owned spawn sessions verify host.ready and results against the claimed binding before publishing a handle.
- [Phase HW-01]: The child carrier and POST /bus share a bounded NIP-5D-shaped envelope with raw attachments and generic binding dispatch.
- [Phase ?]: Manifest version incompatibility, API incompatibility, and unknown metadata are diagnosed before catalog records reach resolution or resource claims.
- [Phase ?]: Typed startup configuration resolves binding > plugin > global > manifest into immutable values through one binary TOML seam.
- [Phase ?]: Secret-bearing settings accept only credential, file, or inherited-descriptor references; manifests and diagnostics never carry secret values.

### Roadmap Evolution

- Phase 1 added: Capability-Oriented Hardware Runtime

### Pending Todos

None yet.

### Blockers/Concerns

- IPC encoding and driver-process granularity need measurement on Pi-class
  hardware before the runtime contract is frozen.

## Session Continuity

Last session: 2026-08-26T11:01:37.197Z
Stopped at: Completed HW-01-05-PLAN.md
Resume file: None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase HW-01 P01 | 4m | 1 tasks | 8 files |
| Phase HW-01-capability-oriented-hardware-runtime P02 | 5m | 1 tasks | 14 files |
| Phase HW-01-capability-oriented-hardware-runtime P03 | 4m | 1 tasks | 11 files |
| Phase HW-01-capability-oriented-hardware-runtime P04 | 4m | 1 tasks | 10 files |
| Phase HW-01 P05 | 5m | 1 tasks | 10 files |
