---
phase: HW-01-capability-oriented-hardware-runtime
reviewed: 2026-08-26T18:31:25Z
depth: standard
files_reviewed: 193
files_reviewed_list:
  - docs/hardware-driver-benchmark.md
  - docs/hardware-driver-runtime.md
  - packages/totem-driver-api/pyproject.toml
  - packages/totem-driver-api/src/totem_driver_api/__init__.py
  - packages/totem-driver-api/src/totem_driver_api/capabilities/nfc.py
  - packages/totem-driver-api/src/totem_driver_api/capabilities/power.py
  - packages/totem-driver-api/src/totem_driver_api/capabilities/radio/bluetooth.py
  - packages/totem-driver-api/src/totem_driver_api/capabilities/radio/wifi.py
  - packages/totem-driver-api/src/totem_driver_api/capabilities/storage.py
  - packages/totem-driver-api/src/totem_driver_api/conformance/suite.py
  - packages/totem-driver-api/src/totem_driver_api/lifecycle.py
  - packages/totem-driver-api/src/totem_driver_api/manifest.py
  - packages/totem-driver-api/src/totem_driver_api/messages.py
  - packages/totem-driver-api/src/totem_driver_api/resources.py
  - pyproject.toml
  - scripts/benchmark_driver_host.py
  - src/totem/__main__.py
  - src/totem/api/app.py
  - src/totem/api/event_manager.py
  - src/totem/compat/hardware_client.py
  - src/totem/compat/hardware_env.py
  - src/totem/devices/contracts.py
  - src/totem/devices/display/__init__.py
  - src/totem/devices/display/display.py
  - src/totem/devices/display/drivers/_waveshare_2in13_base.py
  - src/totem/devices/display/drivers/mock_eink.py
  - src/totem/devices/display/drivers/waveshare_2in13.py
  - src/totem/devices/display/drivers/waveshare_2in13_pi5.py
  - src/totem/devices/display/drivers/waveshare_2in13_pi5_sw_cs.py
  - src/totem/devices/display/drivers/waveshare_2in13_v1.py
  - src/totem/devices/display/drivers/waveshare_2in13_v2.py
  - src/totem/devices/display/drivers/waveshare_2in13_v3.py
  - src/totem/devices/display/drivers/waveshare_2in13_v4.py
  - src/totem/devices/display/drivers/waveshare_3in7.py
  - src/totem/devices/display/drivers/waveshare_3in7_pi5.py
  - src/totem/devices/display/waveshare_epd/__init__.py
  - src/totem/devices/display/waveshare_epd/epd3in7.py
  - src/totem/devices/display/waveshare_epd/epdconfig.py
  - src/totem/devices/network/bluetooth.py
  - src/totem/devices/network/dbus_runtime.py
  - src/totem/devices/network/drivers/__init__.py
  - src/totem/devices/network/drivers/mock_wifi.py
  - src/totem/devices/network/drivers/network_manager_wifi.py
  - src/totem/devices/network/drivers/rpi5_onboard_wifi.py
  - src/totem/devices/network/drivers/usb_wifi_adapter.py
  - src/totem/devices/network/errors.py
  - src/totem/devices/network/models.py
  - src/totem/devices/network/nan.py
  - src/totem/devices/network/network.py
  - src/totem/devices/nfc/__init__.py
  - src/totem/devices/nfc/drivers/acr122.py
  - src/totem/devices/nfc/drivers/mock_nfc.py
  - src/totem/devices/nfc/drivers/pn532.py
  - src/totem/devices/nfc/nfc.py
  - src/totem/devices/registry.py
  - src/totem/devices/storage/__init__.py
  - src/totem/devices/storage/device.py
  - src/totem/devices/storage/files.py
  - src/totem/devices/ups/drivers/pisugar2.py
  - src/totem/devices/ups/drivers/waveshare_ups_hat_c.py
  - src/totem/devices/ups/ups.py
  - src/totem/hardware/api/app.py
  - src/totem/hardware/api/bus.py
  - src/totem/hardware/api/events.py
  - src/totem/hardware/api/health.py
  - src/totem/hardware/builtin/display/drivers/_waveshare_2in13_base.py
  - src/totem/hardware/builtin/display/drivers/mock_eink.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_pi5.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_pi5_sw_cs.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v1.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v2.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v3.py
  - src/totem/hardware/builtin/display/drivers/waveshare_2in13_v4.py
  - src/totem/hardware/builtin/display/drivers/waveshare_3in7.py
  - src/totem/hardware/builtin/display/drivers/waveshare_3in7_pi5.py
  - src/totem/hardware/builtin/display/provider.py
  - src/totem/hardware/builtin/display/totem-driver-manifest.json
  - src/totem/hardware/builtin/display/waveshare_epd/epd3in7.py
  - src/totem/hardware/builtin/display/waveshare_epd/epdconfig.py
  - src/totem/hardware/builtin/nfc/provider.py
  - src/totem/hardware/builtin/nfc/totem-driver-manifest.json
  - src/totem/hardware/builtin/power/provider.py
  - src/totem/hardware/builtin/power/totem-driver-manifest.json
  - src/totem/hardware/builtin/radio/bluetooth-manifest.json
  - src/totem/hardware/builtin/radio/bluetooth_provider.py
  - src/totem/hardware/builtin/radio/dbus_runtime.py
  - src/totem/hardware/builtin/radio/drivers/bluez.py
  - src/totem/hardware/builtin/radio/drivers/mock_bluetooth.py
  - src/totem/hardware/builtin/radio/drivers/network_manager_wifi.py
  - src/totem/hardware/builtin/radio/l2cap.py
  - src/totem/hardware/builtin/radio/nan.py
  - src/totem/hardware/builtin/radio/totem-driver-manifest.json
  - src/totem/hardware/builtin/radio/wifi-manifest.json
  - src/totem/hardware/builtin/radio/wifi_provider.py
  - src/totem/hardware/builtin/storage/provider.py
  - src/totem/hardware/builtin/storage/totem-driver-manifest.json
  - src/totem/hardware/capabilities/__init__.py
  - src/totem/hardware/capabilities/base.py
  - src/totem/hardware/capabilities/display.py
  - src/totem/hardware/capabilities/nfc.py
  - src/totem/hardware/capabilities/power.py
  - src/totem/hardware/capabilities/radio/bluetooth.py
  - src/totem/hardware/capabilities/radio/shared.py
  - src/totem/hardware/capabilities/radio/wifi.py
  - src/totem/hardware/capabilities/storage.py
  - src/totem/hardware/catalog/diagnostics.py
  - src/totem/hardware/catalog/manifests.py
  - src/totem/hardware/catalog/metadata.py
  - src/totem/hardware/discovery/facts.py
  - src/totem/hardware/discovery/inventory.py
  - src/totem/hardware/discovery/profiles.py
  - src/totem/hardware/discovery/resolver.py
  - src/totem/hardware/hosts/base.py
  - src/totem/hardware/hosts/in_process.py
  - src/totem/hardware/hosts/process.py
  - src/totem/hardware/hosts/protocol.py
  - src/totem/hardware/hosts/unix.py
  - src/totem/hardware/hosts/worker.py
  - src/totem/hardware/runtime/__init__.py
  - src/totem/hardware/runtime/bindings.py
  - src/totem/hardware/runtime/broker.py
  - src/totem/hardware/runtime/config.py
  - src/totem/hardware/runtime/events.py
  - src/totem/hardware/runtime/health.py
  - src/totem/hardware/runtime/lifecycle.py
  - src/totem/hardware/runtime/runtime.py
  - src/totem/hardware/runtime/supervisor.py
  - src/totem/managers/display_manager.py
  - src/totem/managers/network_manager.py
  - src/totem/managers/nfc_manager.py
  - src/totem/managers/storage_manager.py
  - src/totem/managers/ups_manager.py
  - src/totem/screen/__main__.py
  - src/totem/screen/adapters/__init__.py
  - src/totem/screen/adapters/hardware_bus.py
  - src/totem/screen/controller.py
  - src/totem/screen/display.py
  - src/totem/screen/ports.py
  - src/totem/screen/readiness.py
  - tests/benchmarks/hardware_runtime/harness.py
  - tests/conftest.py
  - tests/fixtures/hardware_runtime/protocol-vectors.json
  - tests/fixtures/totem-driver-fixture/pyproject.toml
  - tests/hardware/test_driver_host_bench.py
  - tests/unit/hardware_runtime/conftest.py
  - tests/unit/hardware_runtime/test_broker.py
  - tests/unit/hardware_runtime/test_builtin_bluetooth.py
  - tests/unit/hardware_runtime/test_builtin_display_2in13_variants.py
  - tests/unit/hardware_runtime/test_builtin_display_aux_variants.py
  - tests/unit/hardware_runtime/test_builtin_display_core.py
  - tests/unit/hardware_runtime/test_builtin_nfc.py
  - tests/unit/hardware_runtime/test_builtin_power.py
  - tests/unit/hardware_runtime/test_builtin_storage.py
  - tests/unit/hardware_runtime/test_builtin_wifi.py
  - tests/unit/hardware_runtime/test_catalog.py
  - tests/unit/hardware_runtime/test_catalog_claim_tracer.py
  - tests/unit/hardware_runtime/test_config.py
  - tests/unit/hardware_runtime/test_conformance.py
  - tests/unit/hardware_runtime/test_import_boundaries.py
  - tests/unit/hardware_runtime/test_in_process_host.py
  - tests/unit/hardware_runtime/test_lifecycle.py
  - tests/unit/hardware_runtime/test_manifest.py
  - tests/unit/hardware_runtime/test_process_host.py
  - tests/unit/hardware_runtime/test_protocol.py
  - tests/unit/hardware_runtime/test_public_api_fixture.py
  - tests/unit/hardware_runtime/test_radio_resources.py
  - tests/unit/hardware_runtime/test_radio_shared_support.py
  - tests/unit/hardware_runtime/test_resolver.py
  - tests/unit/hardware_runtime/test_runtime.py
  - tests/unit/hardware_runtime/test_runtime_tracer.py
  - tests/unit/test_api_facades.py
  - tests/unit/test_cli_compat.py
  - tests/unit/test_device_display_power_facades.py
  - tests/unit/test_device_nfc_storage_facades.py
  - tests/unit/test_device_radio_facades.py
  - tests/unit/test_display_2in13_compat.py
  - tests/unit/test_display_aux_compat.py
  - tests/unit/test_driver_contracts.py
  - tests/unit/test_driver_registry.py
  - tests/unit/test_hardware_bus.py
  - tests/unit/test_manager_facades.py
  - tests/unit/test_mock_transports.py
  - tests/unit/test_phase1_regression.py
  - tests/unit/test_pisugar2.py
  - tests/unit/test_radio_api.py
  - tests/unit/test_radio_primitives.py
  - tests/unit/test_registry_facade.py
  - tests/unit/test_screen.py
  - tests/unit/test_service_api.py
  - tests/unit/test_storage.py
  - tests/unit/test_systemd_contracts.py
  - tests/unit/test_wifi_provider_compat.py
findings:
  critical: 6
  warning: 1
  info: 0
  total: 7
status: issues_found
---

# Phase HW-01: Code Review Report

**Reviewed:** 2026-08-26T18:31:25Z
**Depth:** standard
**Files Reviewed:** 193
**Status:** issues_found

## Summary

The summary frontmatter declares 193 existing non-planning files (five more than the supplied 188-file count because Plans 06 and 07 use inline YAML lists); all 193 were parsed/reviewed. The local unit suite passes (470 tests), but the deployed composition never resolves or starts a binding, the compatibility facade cannot produce requests accepted by the canonical bus, and the child host has no composition data for any built-in provider. The architecture therefore cannot perform a real hardware operation despite fixture-level green tests.

## Critical Issues

### CR-01: Default deployed startup constructs an empty, permanently unusable runtime — **BLOCKER**

**File:** `src/totem/__main__.py:30-46`

**Issue:** Both deployed commands call `compose_application()`, which selects `_empty_runtime` when no test-only factory is injected (line 61). That owner contains no bindings and its host factory is deliberately unreachable. Repository-wide composition search finds no production caller that scans the catalog, collects facts, resolves a plan, acquires claims, or builds a process/in-process host. Consequently every real capability request has no binding to dispatch to.

**Fix:** Replace `_empty_runtime` with production composition that builds one immutable plan (catalog → facts/profile → resolver → broker → selected host factory) and injects that `HardwareRuntime`. Keep an explicit empty runtime only for a documented no-hardware mode, not as the deployed default.

### CR-02: Process workers receive no selected binding configuration or child resources, so all built-in providers start unconfigured — **BLOCKER**

**File:** `src/totem/hardware/hosts/worker.py:55-60`

**Issue:** The worker imports the entry point and invokes its factory with zero arguments. `ProcessDriverHost.start_group` passes only fd, entry point, session, generation, and binding IDs at `src/totem/hardware/hosts/process.py:70-80`; it never transfers resolved settings, claims, or approved descriptors. The factories therefore return unusable defaults: for example the display factory returns `DisplayProvider()` at `src/totem/hardware/builtin/display/provider.py:95-103`, power returns `PowerProvider()` at `src/totem/hardware/builtin/power/provider.py:80-83`, and both radio factories use `"unbound"` identifiers at `wifi_provider.py:201-204` and `bluetooth_provider.py:193-196`. Their first real action rejects selection/claim validation instead of touching a driver.

**Fix:** Define a bounded child bootstrap contract carrying the selected binding ID, non-secret effective settings, normalized granted claims, and explicitly passed credentials/descriptors. Have each provider factory consume that bootstrap and construct its child-only transport/driver. Exercise it through the production `ProcessDriverHost`, not direct constructor fixtures.

### CR-03: Legacy routes cannot form a request the canonical bus or worker will execute — **BLOCKER**

**File:** `src/totem/compat/hardware_client.py:106-142`

**Issue:** `LegacyHardwareClient.call` never supplies `binding_id`, while `HardwareBus.dispatch` rejects every capability request lacking one at `src/totem/hardware/api/bus.py:81-85`. Its dynamic adapter then serializes every operation as generic `args`/`kwargs` (lines 126-140), whereas the worker requires operation-specific fields such as `path`/ `data_b64` at `src/totem/hardware/hosts/worker.py:119-145` and frame metadata at lines 188-203. It also maps display text to `display.text.write` and radio operations to `radio.wifi.*`/`radio.bluetooth.*` (lines 13 and 24-73), but the worker accepts neither those spellings nor the full advertised legacy operation surface. With a non-empty runtime these calls still return `binding_unavailable`, `unknown_type`, or `invalid_request`.

**Fix:** Replace generic `__getattr__` forwarding with explicit facade translators that select an approved binding and emit the exact public capability request schema. Either expose binding selection in the client constructor/configuration or have the runtime resolve a deterministic default binding. Add end-to-end tests using `HardwareBus` plus the worker contract for display, storage, NFC, Wi-Fi, and Bluetooth.

### CR-04: The supposedly extensible plugin boundary is a closed core type switch — **BLOCKER**

**File:** `src/totem/hardware/hosts/worker.py:87-210`

**Issue:** The child host hardcodes every message type, request DTO, provider method, and result shape. The parent bus repeats this registry in `src/totem/hardware/api/bus.py:12-20,93-100`, while `HardwareRuntime` repeats capability-family selection in `src/totem/hardware/runtime/runtime.py:216-229`. Installing a third-party provider with a new independently versioned capability necessarily requires editing three canonical modules, contradicting the phase's no-central-registry/independent-provider contract.

**Fix:** Move operation dispatch into the selected provider through a versioned SPI method (for example `provider.dispatch(logical_message, attachments, context)`). The core should validate envelope, session, capability/binding authorization, and result correlation generically; manifests/provider metadata should describe routing without a family switch in the runtime.

### CR-05: A host-factory startup failure leaks the just-acquired resource leases — **BLOCKER**

**File:** `src/totem/hardware/runtime/supervisor.py:210-215`

**Issue:** `_start_group` acquires leases and only then calls the injected host factory. If the factory raises before assigning `host`, the generic exception branch at lines 242-248 only releases when `"host" in locals()`; it records failure and exits while the broker retains every acquired lease. Later starts conflict indefinitely even though no child was ever created.

**Fix:** Track acquisition separately from host creation. On every failure after `acquire_many`, release the exact leases when no host exists; when a host exists, use the existing confirmed-death sequence before release. Add a fault-injection test where `host_factory` raises immediately and assert an empty broker snapshot.

### CR-06: Benchmark acceptance can be fabricated from local/synthetic data — **BLOCKER**

**File:** `scripts/benchmark_driver_host.py:85-165`

**Issue:** `validate_evidence` accepts any caller-authored JSON record; it has no `hardware_contacted`/evidence-scope assertion, no trusted provenance, and accepts `runtime.mode == "in_process"` (lines 106-112) even though the pinned comparison cases are process-host cases. It only requires a non-empty arbitrary `provider_imports` list (lines 119-121), does not compare it with the pinned workload, and `_number` accepts non-finite values such as JSON `NaN` (lines 52-60). Supplying two invented records, one per grouping, makes `architecture_acceptance` report `accepted: true` at lines 184-197, so controller output can be presented as Pi acceptance.

**Fix:** Require and validate immutable capture provenance (`evidence_scope: allocated-hardware`, `hardware_contacted: true`, allocated target identity, collection timestamp, and operator/device attestation), require process mode and exact pinned workload fields, reject non-finite numbers with `math.isfinite`, and reject duplicate/extra grouping rows. Do not emit an accepted matrix without validated device-origin evidence.

## Warnings

### WR-01: Deployment and facade tests are false-positive seams because they replace the failing production boundary — **WARNING**

**File:** `tests/unit/test_cli_compat.py:17-30`

**Issue:** The composition test injects a fake runtime whose `handle` always raises and explicitly says it does not dispatch hardware. Similarly, `tests/unit/test_api_facades.py:20-32` and `tests/unit/test_service_api.py:19-42` use permissive fake buses that return success for arbitrary messages. These tests cannot detect the empty runtime, missing binding ID, incompatible payload schema, or worker routing failures above; this explains why the 470-test suite is green.

**Fix:** Retain unit fakes for translator isolation, but add a production-shape integration test that calls default `compose_application` with a controlled catalog/facts fixture, starts a real process-host fixture, and sends representative legacy routes through `LegacyHardwareClient → HardwareBus → worker`. Assert a real binding is selected, the provider receives the expected request/attachment, and resources are released at shutdown.

---

_Reviewed: 2026-08-26T18:31:25Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_

