---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: Capability-Oriented Hardware Runtime
status: executing
stopped_at: Completed HW-01-19-PLAN.md
last_updated: "2026-08-26T14:21:20.438Z"
last_activity: 2026-08-22
last_activity_desc: Phase 1 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 33
  completed_plans: 19
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-22)

**Core value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.
**Current focus:** Phase 1 — Capability-Oriented Hardware Runtime

## Current Position

Phase: 1 (Capability-Oriented Hardware Runtime) — EXECUTING
Plan: 19 of 33
Status: Ready to execute
Last activity: 2026-08-22 — Phase 1 execution started

Progress: ░░░░░░░░░░ [██████░░░░] 58%

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
- [Phase ?]: Codec 1 is canonical UTF-8 JSON; codec 2 remains reserved and rejected.
- [Phase ?]: Driver request correlation is generation-scoped so stale results cannot satisfy a replacement host.
- [Phase HW-01]: Observed predicate evidence outranks supplemental profile evidence; profiles cannot satisfy resources or service prerequisites.
- [Phase HW-01]: Explicit bindings select a provider only after capability, config, prerequisite, and resource validation.
- [Phase ?]: Resource broker atomically grants normalized claim sets or none, with deterministic conflict owners.
- [Phase ?]: Lease release requires the active binding, generation, and opaque owner token; snapshots redact credentials.
- [Phase ?]: Lifecycle transitions are explicit and locked; required readiness is derived independently from optional binding degradation.
- [Phase ?]: Process lease release requires invalidation, terminate-or-kill, confirmed exit, and carrier closure before broker release.
- [Phase ?]: Provider identity/version is the default process group; per-binding grouping is an explicit manifest override.
- [Phase ?]: In-process calls use the existing strict frame codec and live invocations contaminate rather than being claimed killed.
- [Phase ?]: Host mode resolves binding > plugin > global > manifest with process as the default.
- [Phase ?]: The display manifest resolves the Waveshare 2.13 family from data-only profile evidence; a configured panel variant remains a child-composition concern.
- [Phase ?]: Display provider construction is side-effect-free and accepts only injected transports after exact SPI/GPIO claim validation.
- [Phase ?]: All Waveshare 2.13 variants use the provider-owned injected base; concrete modules preserve controller-specific command and framebuffer behavior.
- [Phase ?]: Pi 5 hardware-CS and software-CS variants are explicit concrete transport kinds with no import-time device probing.
- [Phase ?]: Vendored 3.7 support stays child-only and catalog coverage enumerates it by source path without importing hardware-active modules.
- [Phase ?]: mock_eink remains an explicit test transport and is excluded from the production display manifest.
- [Phase ?]: Legacy 2.13 facades preserve canonical class identity rather than wrapping or subclassing provider classes.
- [Phase ?]: Obsolete DeviceDriver inheritance assertions remain a dependency-ordered migration window for Plan 01-28 because satisfying them now would violate API-05 clean-break ownership.
- [Phase ?]: Legacy auxiliary display facades preserve canonical identity; vendor support is source-audited without hardware-active imports.
- [Phase ?]: Obsolete mock/3.7 DeviceDriver and health assertions join the existing Plan 01-28 migration window.
- [Phase ?]: Power telemetry requires an explicit model, matching I2C address evidence, and acquired I2C lease before provider access.
- [Phase ?]: Canonical UPS drivers preserve telemetry shapes without legacy DeviceDriver inheritance; Plan 01-28 owns stale inheritance checks.
- [Phase ?]: Use nfc.tag@1 bounded base64 values so malformed or oversized writes fail before transport I/O.
- [Phase ?]: Require exact non-mock evidence plus leased NFC reader claims; mock NFC is explicit test configuration only.
- [Phase ?]: Defer four obsolete NFC legacy-contract assertions to Plan 01-28 rather than restore legacy inheritance.
- [Phase ?]: Storage uses storage.files@1 bounded base64 values and normalized relative POSIX paths before dispatch.
- [Phase ?]: Storage requires exclusive root, mount, and block leases before injected driver initialization.
- [Phase ?]: Wi-Fi and Bluetooth publish separate major-versioned data contracts; backend sessions remain a later provider concern.
- [Phase ?]: Radio coexistence is an explicit symmetric matrix scoped to matching PHY and compatibility group, so independent radios never contend through a global lock.
- [Phase ?]: Provider-side D-Bus support accepts an injected call seam and names services only; it owns neither a bus connection nor a backend session.

### Roadmap Evolution

- Phase 1 added: Capability-Oriented Hardware Runtime

### Pending Todos

None yet.

### Blockers/Concerns

- IPC encoding and driver-process granularity need measurement on Pi-class
  hardware before the runtime contract is frozen.

## Session Continuity

Last session: 2026-08-26T14:21:20.432Z
Stopped at: Completed HW-01-19-PLAN.md
Resume file: None

## Performance Metrics

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase HW-01 P01 | 4m | 1 tasks | 8 files |
| Phase HW-01-capability-oriented-hardware-runtime P02 | 5m | 1 tasks | 14 files |
| Phase HW-01-capability-oriented-hardware-runtime P03 | 4m | 1 tasks | 11 files |
| Phase HW-01-capability-oriented-hardware-runtime P04 | 4m | 1 tasks | 10 files |
| Phase HW-01 P05 | 5m | 1 tasks | 10 files |
| Phase HW-01-capability-oriented-hardware-runtime P08 | 24m | 2 tasks | 8 files |
| Phase HW-01 P06 | 8min | 1 tasks | 8 files |
| Phase HW-01 P07 | 7m | 1 tasks | 2 files |
| Phase HW-01 P09 | 40m | 2 tasks | 12 files |
| Phase HW-01 P10 | 31m | 2 tasks | 11 files |
| Phase HW-01 P11 | 5m | 1 tasks | 8 files |
| Phase HW-01 P12 | 4m | 1 tasks | 8 files |
| Phase HW-01 P13 | 12min | 1 tasks | 7 files |
| Phase HW-01 P14 | 5min | 1 tasks | 10 files |
| Phase HW-01 P15 | 4min | 1 tasks | 7 files |
| Phase HW-01 P16 | 12min | 1 tasks | 15 files |
| Phase HW-01-capability-oriented-hardware-runtime P17 | 4min | 1 tasks | 16 files |
| Phase HW-01 P18 | 40min | 1 tasks | 16 files |
| Phase HW-01 P19 | 15min | 1 tasks | 13 files |
