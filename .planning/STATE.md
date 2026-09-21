---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: Capability-Oriented Hardware Runtime
status: executing
stopped_at: Completed HW-01-33-PLAN.md
last_updated: "2026-08-26T18:21:26.887Z"
last_activity: 2026-08-22
last_activity_desc: Phase 1 execution started
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 33
  completed_plans: 33
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-08-22)

**Core value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.
**Current focus:** Phase 1 — Capability-Oriented Hardware Runtime

## Current Position

Phase: 1 (Capability-Oriented Hardware Runtime) — EXECUTING
Plan: 33 of 33
Status: Ready to execute
Last activity: 2026-08-22 — Phase 1 execution started

Progress: ░░░░░░░░░░ [██████████] 100%

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
- [Phase ?]: Wi-Fi validates leased NetworkManager service, interface, and PHY facts before driver composition; caller payloads never select identities.
- [Phase ?]: The existing catalog filename remains authoritative, so the requested Wi-Fi declaration is accompanied by a package-discoverable totem-driver-manifest.json copy.
- [Phase ?]: Canonical Wi-Fi modules own their shared radio models, errors, parsers, D-Bus runtime, and session interface; legacy errors are compatibility-only re-exports.
- [Phase ?]: Each historical Wi-Fi/support path re-exports its complete canonical public surface with a single import-only statement.
- [Phase ?]: Compatibility verification treats package __init__.py facades as first-class inventory members and compares signatures only when Python exposes one.
- [Phase ?]: BlueZ composition validates leased D-Bus, adapter, and PHY facts while Wi-Fi coexistence remains broker policy.
- [Phase ?]: Provider-local package-data manifests enable multiple independent built-ins without importing entry points.
- [Phase ?]: One lifespan-scoped runtime owns hosts and releases ownership only after clean shutdown.
- [Phase ?]: Applications receive opaque capability/binding handles; provider objects never escape the runtime.
- [Phase ?]: Loopback bus access trusts only the ASGI peer address; forwarded headers never grant hardware access.
- [Phase ?]: The hardware app owns exactly one injected or factory-created runtime and exposes lossy SSE backpressure only as an aggregate counter.
- [Phase ?]: Screen owns rendering and boot behavior while consuming only narrow frame, health, and power ports.
- [Phase ?]: Screen frames use bounded raw canonical-bus attachments instead of legacy base64 image routes.
- [Phase ?]: hardware.status.get projects only ready/degraded values so screen readiness never imports runtime models or calls /health.
- [Phase ?]: Legacy REST handlers retain response models but delegate through one injected LegacyHardwareClient.
- [Phase ?]: Legacy environment names are parsed only in totem.compat.hardware_env into typed configuration.
- [Phase ?]: Legacy manager constructor selections remain inert compatibility config; managers never construct, probe, or select hardware.
- [Phase ?]: NetworkManager aggregates separate Wi-Fi and Bluetooth client actions while coexistence remains broker policy.
- [Phase ?]: Manager close is facade-local so shared injected clients and the sole runtime stay live.
- [Phase ?]: Legacy registry records derive only from catalog metadata and can request only existing canonical runtime handles.
- [Phase ?]: DriverState aliases public BindingState; DeviceDriver no longer infers lifecycle, mock state, or ownership.
- [Phase ?]: Legacy manager integration tests use explicit local client fakes; tests do not construct direct mock drivers through manager facades.
- [Phase ?]: Display and UPS selection names are inert compatibility configuration; lifecycle methods stay facade-local while operations use the shared canonical client.
- [Phase ?]: NFC and storage selection inputs remain inert compatibility config; all operations delegate through LegacyHardwareClient.
- [Phase ?]: NFC and storage facade initialize/close are local transitions so the canonical runtime exclusively owns leases and providers.
- [Phase ?]: Keep Wi-Fi and Bluetooth driver selections as inert compatibility configuration; wrappers cannot select local backends.
- [Phase ?]: Route radio families through distinct canonical client operations while shared-PHY admission stays broker policy.
- [Phase ?]: Startup parses legacy environment only at the outward boundary and passes typed configuration inward.
- [Phase ?]: The totem-api entry point reuses totem.__main__.compose_application so both API command names construct one canonical runtime shape.
- [Phase ?]: Pi evidence is validated only from explicit allocated-device records; the benchmark tool never discovers or contacts a target.
- [Phase ?]: Canonical JSON and provider-default grouping remain provisional until complete armv6l, armv7l, and aarch64 evidence is captured.

### Roadmap Evolution

- Phase 1 added: Capability-Oriented Hardware Runtime

### Pending Todos

None yet.

### Blockers/Concerns

- IPC encoding and driver-process granularity need measurement on Pi-class
  hardware before the runtime contract is frozen.

## Session Continuity

Last session: 2026-08-26T18:21:26.879Z
Stopped at: Completed HW-01-33-PLAN.md
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
| Phase HW-01 P20 | 13min | 1 tasks | 16 files |
| Phase HW-01 P21 | 3min | 1 tasks | 10 files |
| Phase HW-01 P22 | 8m | 1 tasks | 16 files |
| Phase HW-01 P23 | 10m | 1 tasks | 14 files |
| Phase HW-01 P24 | 24m | 1 tasks | 7 files |
| Phase HW-01 P25 | 4m | 2 tasks | 10 files |
| Phase HW-01 P26 | 25min | 1 tasks | 9 files |
| Phase HW-01 P27 | 8m | 1 tasks | 7 files |
| Phase HW-01 P28 | 18m | 1 tasks | 5 files |
| Phase HW-01 P29 | 2m | 1 tasks | 4 files |
| Phase HW-01 P30 | 2m | 1 tasks | 8 files |
| Phase HW-01 P31 | 3m | 1 tasks | 3 files |
| Phase HW-01 P32 | 17m | 1 tasks | 6 files |
| Phase HW-01 P33 | 12m | 2 tasks | 8 files |
