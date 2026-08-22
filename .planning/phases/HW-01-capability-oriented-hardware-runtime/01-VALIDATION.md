---
phase: 1
slug: capability-oriented-hardware-runtime
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-22
---

# Phase 1 — Validation Strategy

All Python and pytest claims use the controlled `.venv/bin/python` created by **01-01 Task 1**. No implementation plan may substitute an ambient `python` or `python3` command. Hardware remains opt-in and requires explicit allocation.

## Test infrastructure

| Property | Value |
|---|---|
| Framework | `pytest >=7.3,<9.0` under Python >=3.9 |
| Config | `pyproject.toml` |
| Controlled interpreter | `.venv/bin/python` |
| Quick gate | `.venv/bin/python -m pytest tests/unit/hardware_runtime -x` |
| Full local gate | `.venv/bin/python -m pytest tests/unit -x` |
| Hardware gate | Deferred; `--run-hardware` plus explicit target/allocation only |
| Feedback timing | Measured and recorded by 01-01 Task 1 before tracer evidence |

Sampling: run the task-specific command after each task; run the hardware-runtime quick gate after each wave; run the full local gate in 01-33 Task 2. Target quick feedback is under 60 seconds; actual durations supersede the target once measured.

## Exact plan/task validation map

| Wave | Plan/task | Requirements implemented | Automated command | Status |
|---:|---|---|---|---|
| 1 | 01-01 T1 — controlled environment, fakes, vectors, import guard, harness shell | TST-04 infrastructure | `test -x .venv/bin/python && .venv/bin/python -c 'import sys; assert sys.version_info >= (3, 9)' && .venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 2 | 01-02 T1 — public API and independent fixture wheel | HWR-02, SPI-02 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_public_api_fixture.py -x` | pending |
| 3 | 01-03 T1 — installed-fixture catalog→resolve→claim tracer | HWR-03, SPI-01 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -x` | pending |
| 4 | 01-04 T1 — claimed binding→child host→handle→bus tracer | HWR-02, SPI-06 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime_tracer.py -x` | pending |
| 5 | 01-05 T1 — manifest/catalog and typed config | SPI-03, SPI-04, SPI-05 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog.py tests/unit/hardware_runtime/test_config.py -x` | pending |
| 5 | 01-08 T1 — logical envelope/correlation | ISO-03 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -k 'logical or correlation or unknown' -x` | pending |
| 5 | 01-08 T2 — framed JSON and attachments | ISO-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -x` | pending |
| 6 | 01-06 T1 — facts, profiles, resolver evidence | HWR-01, CMP-01, CMP-02, CMP-03, CMP-04, TST-02 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py -x` | pending |
| 7 | 01-07 T1 — normalized atomic broker | RUN-02 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_broker.py -x` | pending |
| 8 | 01-09 T1 — lifecycle/readiness/events | RUN-01 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py -x` | pending |
| 8 | 01-09 T2 — process host/supervisor/recovery | ISO-01, ISO-05, ISO-07 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py -x` | pending |
| 9 | 01-10 T1 — configurable in-process host | **ISO-02**, ISO-06 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -x` | pending |
| 9 | 01-10 T2 — shared dual-host conformance | TST-01 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py tests/unit/hardware_runtime/test_in_process_host.py -x` | pending |
| 10 | 01-11 T1 — display core/common contract | HWR-02, SPI-06 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_core.py -x` | pending |
| 11 | 01-12 T1 — complete 2.13 display variant family | HWR-02, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py -x` | pending |
| 11 | 01-13 T1 — auxiliary display variants/support | HWR-02, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_display_aux_variants.py tests/unit/test_mock_transports.py -x` | pending |
| 12 | 01-14 T1 — 2.13 compatibility re-exports | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_display_2in13_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 12 | 01-15 T1 — auxiliary display compatibility re-exports | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_display_aux_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 13 | 01-16 T1 — power provider | HWR-02, SPI-06, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_power.py tests/unit/test_pisugar2.py tests/unit/test_waveshare_ups_hat_c.py -x` | pending |
| 14 | 01-17 T1 — NFC provider | HWR-02, SPI-06, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_nfc.py -x` | pending |
| 15 | 01-18 T1 — storage provider/path scope | HWR-02, SPI-06, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_storage.py tests/unit/test_storage.py -x` | pending |
| 16 | 01-19 T1 — radio contracts/shared support/coexistence | API-02, RUN-03 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_radio_resources.py tests/unit/hardware_runtime/test_radio_shared_support.py -x` | pending |
| 17 | 01-20 T1 — Wi-Fi provider/session behavior | API-02, RUN-03, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_wifi.py tests/unit/test_radio_primitives.py -k 'wifi or nan' -x` | pending |
| 18 | 01-21 T1 — Wi-Fi/support compatibility re-exports | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_wifi_provider_compat.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 19 | 01-22 T1 — Bluetooth provider | API-02, RUN-03, TST-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_builtin_bluetooth.py tests/unit/test_radio_primitives.py -k 'bluetooth or bluez or l2cap or gatt' -x` | pending |
| 20 | 01-23 T1 — sole eager runtime/handles | HWR-04 | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py -x` | pending |
| 21 | 01-24 T1 — loopback bus/SSE | API-01 | `.venv/bin/python -m pytest tests/unit/test_hardware_bus.py -x` | pending |
| 22 | 01-25 T1 — screen ports and bus mapping | API-03 | `.venv/bin/python -m pytest tests/unit/test_screen.py -k 'port or bus or display' -x` | pending |
| 22 | 01-25 T2 — boot/readiness and totem-screen adapter | API-04 | `.venv/bin/python -m pytest tests/unit/test_screen.py -x` | pending |
| 23 | 01-26 T1 — REST/WebSocket/env/client translators | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_service_api.py tests/unit/test_radio_api.py tests/unit/test_api_facades.py -x` | pending |
| 24 | 01-27 T1 — manager facades | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_manager_facades.py tests/unit/test_radio_api.py -k 'manager or facade' -x` | pending |
| 25 | 01-28 T1 — registry/contracts facade | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_driver_registry.py tests/unit/test_driver_contracts.py tests/unit/test_registry_facade.py -x` | pending |
| 26 | 01-29 T1 — display/power wrappers | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_device_display_power_facades.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 26 | 01-30 T1 — NFC/storage wrappers | API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_device_nfc_storage_facades.py tests/unit/test_storage.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 26 | 01-31 T1 — radio wrappers | API-02, API-04, API-05, TST-04 | `.venv/bin/python -m pytest tests/unit/test_device_radio_facades.py tests/unit/test_radio_primitives.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 27 | 01-32 T1 — CLI/env/package/systemd composition | HWR-04, API-04, TST-04 | `.venv/bin/python -m pytest tests/unit/test_cli_compat.py tests/unit/test_systemd_contracts.py tests/unit/hardware_runtime/test_import_boundaries.py -x` | pending |
| 28 | 01-33 T1 — benchmark/runbook/manual gate | ISO-01, TST-03 | `.venv/bin/python -m pytest tests/hardware/test_driver_host_bench.py --collect-only -q && .venv/bin/python scripts/benchmark_driver_host.py --self-test` | pending local / deferred hardware |
| 28 | 01-33 T2 — complete local regression/ledger | HWR-04, TST-04 | `.venv/bin/python -m pytest tests/unit -x && git diff --check` | pending |

## Requirement → concrete implementation owner

| Requirement | Plan/task |
|---|---|
| HWR-01 | 01-06 T1 |
| HWR-02 | 01-02 T1; 01-04 T1; 01-11 T1; 01-12 T1; 01-13 T1; 01-16 T1; 01-17 T1; 01-18 T1 |
| HWR-03 | 01-03 T1 |
| HWR-04 | 01-23 T1; 01-32 T1; 01-33 T2 |
| SPI-01 | 01-03 T1 |
| SPI-02 | 01-02 T1 |
| SPI-03 | 01-05 T1 |
| SPI-04 | 01-05 T1 |
| SPI-05 | 01-05 T1 |
| SPI-06 | 01-04 T1; 01-11 T1; 01-16 T1; 01-17 T1; 01-18 T1 |
| CMP-01 | 01-06 T1 |
| CMP-02 | 01-06 T1 |
| CMP-03 | 01-06 T1 |
| CMP-04 | 01-06 T1 |
| ISO-01 | 01-09 T2; 01-33 T1 |
| **ISO-02** | **01-10 T1 only** |
| ISO-03 | 01-08 T1 |
| ISO-04 | 01-08 T2 |
| ISO-05 | 01-09 T2 |
| ISO-06 | 01-10 T1 |
| ISO-07 | 01-09 T2 |
| RUN-01 | 01-09 T1 |
| RUN-02 | 01-07 T1 |
| RUN-03 | 01-19 T1; 01-20 T1; 01-22 T1 |
| API-01 | 01-24 T1 |
| API-02 | 01-19 T1; 01-20 T1; 01-22 T1; 01-31 T1 |
| API-03 | 01-25 T1 |
| API-04 | 01-14 T1; 01-15 T1; 01-21 T1; 01-25 T2; 01-26 T1; 01-27 T1; 01-28 T1; 01-29 T1; 01-30 T1; 01-31 T1; 01-32 T1 |
| API-05 | 01-14 T1; 01-15 T1; 01-21 T1; 01-26 T1; 01-27 T1; 01-28 T1; 01-29 T1; 01-30 T1; 01-31 T1 |
| TST-01 | 01-10 T2 |
| TST-02 | 01-06 T1 |
| TST-03 | 01-33 T1 |
| TST-04 | 01-01 T1; 01-12 T1; 01-13 T1; 01-14 T1; 01-15 T1; 01-16 T1; 01-17 T1; 01-18 T1; 01-20 T1; 01-21 T1; 01-22 T1; 01-26 T1; 01-27 T1; 01-28 T1; 01-29 T1; 01-30 T1; 01-31 T1; 01-32 T1; 01-33 T2 |

All 33 requirement IDs are present above. ISO-02 has one and only one implementation owner: **01-10 Task 1**.

## Required fault injection

- Child omits `host.ready`; crash and uncooperative hang; cancel→terminate→kill→confirmed wait; stale generation response/event; lease held until confirmed death; bounded backoff and quarantine.
- One-byte fragmented, pipelined, truncated, oversized, unknown codec/version/type, duplicate/correlation, checksum/offset/count mismatch carrier inputs.
- Empty/adjacent/ambiguous facts and plugins; invalid config affecting one binding; secret refs/inherited descriptors; simultaneous conflicting broker claims.
- Cooperative and uncooperative in-process cancellation, contamination, new-work rejection, retained leases, daemon-restart health.
- Compatible and incompatible Wi-Fi/Bluetooth shared-PHY operations with one versus independent adapters.
- Loopback bypass attempts, bounded legacy base64 translation, SSE backpressure/redaction, multiple facade instances against one owner.

## Wave-0 completion checklist

- [ ] 01-01 T1 creates `.venv` with Python >=3.9, installs project tests, and records actual quick/full timing.
- [ ] Fake clock/process/socket/broker/transcript fixtures and protocol vectors exist independently of spike code.
- [ ] AST import guard enforces `totem.hardware` canonical ownership.
- [ ] Benchmark harness shell is collection-safe and cannot contact hardware without explicit opt-in/allocation.
- [ ] 01-02 T1 builds/installs the independent public API and fixture wheels; 01-03 and 01-04 consume them and prove provider import occurs only in the selected child after resolution and claims.

## Manual deferred gates

| Behavior | Requirements | Why manual | Required evidence |
|---|---|---|---|
| Pi startup, PSS, p50/p95 command latency, 4,000-byte frame, event load, crash/hang recovery, post-death leases on armv6l/armv7l/aarch64 | TST-03, ISO-01 | Requires explicitly allocated devices and `/proc` process evidence | Run the Plan 33 pinned workload on each allocated architecture; record architecture, Python/runtime/packages, grouping/mode, PSS (labeled RSS fallback), timings, recovery, generation, lease state, and rollback metadata. |
| Deployed-default cutover | HWR-04, ISO-01, API-04 | One-owner/systemd behavior must be observed on allocated hardware before changing a deployed default | Only after all local gates and complete three-architecture evidence: deploy under rollback, exercise commands/routes/bus, induce child failure, verify recovery/leases, and restore on any failure. |

Controller-only results never satisfy either row. No plan runs `--run-hardware`, SSH, deployment, restart, or live-default mutation.

## Sign-off

- [ ] All 33 plans and every task have a controlled automated command.
- [ ] All 33 requirements map to concrete tasks; ISO-02 maps only to 01-10 T1.
- [ ] The 43-item probe equality in `01-PROBE-LEDGER.md` holds.
- [ ] ASVS L1 applicable controls in `01-SECURITY.md` have task/test evidence.
- [ ] Quick/full feedback durations are measured; all local suites pass; no worker/thread/socket remains.
- [ ] `wave_0_complete` and `nyquist_compliant` become true only after their evidence exists; Pi/cutover remain deferred until allocated.

**Approval:** pending
