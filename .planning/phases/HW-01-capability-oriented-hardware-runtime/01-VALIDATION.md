---
phase: 1
slug: capability-oriented-hardware-runtime
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest >=7.3,<9.0` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/unit -m 'unit and mock_transport' -x` |
| **Full suite command** | `python -m pytest tests/unit -x` |
| **Estimated runtime** | Establish during Wave 0; target feedback latency is under 60 seconds |

The controller did not have a runnable project test environment during phase
research. Wave 0 must create one before implementation evidence can be
accepted. Hardware tests remain opt-in and require explicit bench allocation.

---

## Sampling Rate

- **After every task commit:** Run the narrowest affected unit-test module, or
  `python -m pytest tests/unit -m 'unit and mock_transport' -x` when a task
  crosses module boundaries.
- **After every plan wave:** Run `python -m pytest tests/unit -x`.
- **Before `$gsd-verify-work`:** The full local suite must be green; the
  Pi-class acceptance matrix must be reported separately as passed or deferred.
- **Max feedback latency:** 60 seconds for the quick local gate.

---

## Per-Task Verification Map

The planner assigns final task IDs. Each row below is a mandatory coverage
unit and must be attached to an implementation task before execution begins.

| Coverage Unit | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Public API, catalog, fixture distribution | HWR-02..03, SPI-01..06 | T-01 / T-02 | Manifest and API incompatibilities fail before provider import | unit + install fixture | `python -m pytest tests/unit/hardware_runtime/test_catalog.py -x` | ❌ W0 | ⬜ pending |
| Facts, profiles, deterministic resolution | HWR-01, CMP-01..04 | T-03 | Ambiguity and unmet prerequisites fail closed with stable diagnostics | unit | `python -m pytest tests/unit/hardware_runtime/test_resolver.py -x` | ❌ W0 | ⬜ pending |
| Lifecycle and resource broker | HWR-04, RUN-01..03 | T-04 | Conflicting resources never initialize; one runtime owns every lease | unit | `python -m pytest tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_broker.py -x` | ❌ W0 | ⬜ pending |
| Framed logical protocol | ISO-03..04 | T-05 | Bounded JSON/attachment frames reject malformed, oversized, or mismatched input | unit | `python -m pytest tests/unit/hardware_runtime/test_protocol.py -x` | ❌ W0 | ⬜ pending |
| Process host and supervisor | ISO-01, ISO-05, ISO-07 | T-04 / T-06 | Child death is confirmed before lease release; retry ends in quarantine | unit + mock transport | `python -m pytest tests/unit/hardware_runtime/test_process_host.py -x` | ❌ W0 | ⬜ pending |
| In-process host | ISO-02, ISO-06 | T-07 | Uncooperative work contaminates the binding and retains leases until restart | unit | `python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -x` | ❌ W0 | ⬜ pending |
| Dual-host conformance | TST-01 | T-05 / T-07 | Both hosts produce the same normalized request/result/push transcript | conformance | `python -m pytest tests/unit/hardware_runtime/test_conformance.py -x` | ❌ W0 | ⬜ pending |
| Canonical NIP-5D bus and capability handles | API-01..03 | T-08 | Loopback-only bus validates envelopes and routes by capability handles | API/unit | `python -m pytest tests/unit/test_hardware_bus.py tests/unit/test_screen.py -x` | ❌ W0 / existing migration | ⬜ pending |
| Built-ins and clean-break facades | API-02, API-04..05, TST-04 | T-09 | Facades translate only; canonical modules cannot import legacy ownership code | unit + static layer | `python -m pytest tests/unit/test_legacy_facades.py tests/unit/test_service_api.py -x` | ❌ W0 / existing migration | ⬜ pending |
| Pi-class benchmark harness | TST-03 | T-10 | Results identify host grouping and never infer Pi acceptance from controller data | opt-in hardware | `python -m pytest tests/hardware/test_driver_host_bench.py --run-hardware -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Required Fault Injection

- Child never sends `host.ready`: startup deadline emits `startup_timeout`
  without releasing an unconfirmed owner as if startup had succeeded.
- Malformed prefix/header/attachment, oversize declaration, duplicate IDs,
  checksum mismatch, unsupported codec/version, fragmentation, and pipelining.
- Unknown unsolicited pushes are ignored; unknown requests carrying an `id`
  receive stable `.result` errors.
- Isolated child crash/hang leaves the daemon alive, confirms exit before lease
  release, advances generation, applies bounded backoff, then quarantines.
- Cooperative in-process cancellation leaves later work usable; uncooperative
  work marks the binding `CONTAMINATED`, rejects new work, and retains leases.
- Binding overrides beat automatic matches but cannot bypass API-major,
  configuration, prerequisite, or resource compatibility checks.
- Separate Wi-Fi and Bluetooth requests exercise both denied and permitted
  shared-radio combinations.

---

## Wave 0 Requirements

- [ ] Create/install a Python 3.9-compatible project test environment and
  record the actual quick/full-suite runtimes.
- [ ] Add the public driver-API fixture distribution and an installed-wheel
  fixture registered under `totem.hardware.drivers`.
- [ ] Promote spike protocol and dual-host vectors into production-independent
  test fixtures; production code must not import the spike package.
- [ ] Add fake clock, process, Unix-socket, and resource-broker fixtures.
- [ ] Add a static import-layer test forbidding `totem.hardware` imports from
  legacy `totem.api`, `totem.devices`, and `totem.managers` modules.
- [ ] Add the Pi benchmark harness and evidence template without scheduling a
  bench run.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pi-class startup, PSS, p50/p95 command latency, 4,000-byte frame transfer, event load, kill/hang recovery, and post-death leases on armv6l, armv7l, and aarch64 | TST-03 | Requires explicitly allocated physical Totem devices and process memory data from `/proc` | Run the pinned benchmark workload from the phase runbook on each allocated architecture; capture Python/runtime/package versions, provider-versus-binding grouping, `smaps_rollup` PSS (label RSS fallback), timings, recovery outcome, and lease state. Do not infer acceptance from macOS results. |
| Deployment-default cutover | HWR-04, ISO-01, API-04 | Hardware ownership and systemd behavior must be observed on an allocated device before changing the deployed default | After all local gates pass and allocation is explicit, install the candidate build, verify one runtime owner, exercise legacy commands/routes and the NIP-5D bus, induce a child failure, verify recovery, then restore the prior deployment if any acceptance check fails. |

---

## Validation Sign-Off

- [ ] All planner tasks are mapped to an automated command or an explicit
  Wave 0 dependency.
- [ ] No three consecutive implementation tasks lack automated verification.
- [ ] Wave 0 covers every currently missing test reference.
- [ ] Quick and full commands contain no watch-mode flags.
- [ ] Quick feedback latency is below 60 seconds.
- [ ] All local suites pass.
- [ ] Pi-class evidence is either accepted after explicit allocation or
  explicitly recorded as the remaining cutover gate.
- [ ] `nyquist_compliant: true` is set in frontmatter only after these checks.

**Approval:** pending
