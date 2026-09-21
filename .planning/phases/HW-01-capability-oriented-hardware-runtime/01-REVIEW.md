---
phase: HW-01-capability-oriented-hardware-runtime
reviewed: 2026-08-27T19:19:05Z
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
  critical: 3
  warning: 0
  info: 0
  total: 3
status: issues_found
---

# Phase HW-01: Code Review Report

**Reviewed:** 2026-08-27T19:19:05Z
**Depth:** standard
**Files Reviewed:** 193
**Status:** issues_found

## Summary

All 193 persisted source paths were re-reviewed at standard depth through `13b7348`. The fixes for the signed benchmark path (former CR-06) and built-in child-startup coverage (former WR-01) hold: the controller-safe benchmark subset passes, the documentation includes the controller trust-store argument, and selected child startup validates before `host.ready`. The retained legacy translation table also no longer emits the unrouteable generic envelope.

The phase is still not shippable. Deployment has no producer for the supposedly observed inventory and therefore starts an empty runtime as READY; two preserved routes bypass the controlled compatibility error path; and the in-process conformance/timeout contract is red after dispatch became provider-owned. Local, no-contact checks: the targeted config/process/bus/CLI group passed (25), the radio/systemd/benchmark group passed (29, 1 hardware test deselected), and the full safe suite reaches three deterministic failures (103 passed before `--maxfail=3`). `scripts/benchmark_driver_host.py --self-test` passed as synthetic-only.

## Critical Issues

### CR-01: Deployment has no observed-inventory producer and publishes an empty runtime as healthy — **BLOCKER**

**File:** `deploy/ansible/roles/device_manager/templates/totem-hardware.toml.j2:6-13`

**Issue:** The template now references `totem_hardware_inventory`, but no Ansible task, role default, inventory, or preflight in the reviewed repository defines it. Its `default({})` therefore renders a valid config with an empty `[global.hardware_facts]`. `compose_runtime` accepts those empty facts (`src/totem/hardware/runtime/composition.py:43-54`), resolves no bindings, and `RuntimeLifecycle.snapshot` defines zero required bindings as READY (`src/totem/hardware/runtime/lifecycle.py:220-234`). A local `compose_runtime(RuntimeConfig()).start()` reproduces `bindings=()` with `ready=True`, despite the comment promising an empty owner is never the default. The deployed service consequently looks healthy while offering no hardware capability.

**Fix:** Add a controlled, local deployment preflight that emits a typed `totem_hardware_inventory` fact only from explicit observed evidence (or require the inventory variable and fail the play if absent). Treat an empty non-`no_hardware` plan as failed/degraded, not READY. Add rendered-template/composition tests for missing inventory, intentionally inert `no_hardware`, and present/absent resources.

### CR-02: Two preserved network routes bypass the compatibility boundary and crash with HTTP 500 — **BLOCKER**

**File:** `src/totem/api/app.py:299-311`

**Issue:** `LegacyHardwareClient.__getattr__` deliberately raises `AttributeError` for methods that are neither a translated v1 operation nor in `DEPRECATED_OPERATIONS` (`src/totem/compat/hardware_client.py:107-114`). `get_capabilities` and `get_status` are in neither set, but their deployed routes still call them. With an injected local bus, both `GET /network/capabilities` and `GET /network/status` raise `AttributeError` through FastAPI instead of producing the promised stable 501/compatibility response. The new table test covers only translated actions and misses these routes (`tests/unit/test_radio_api.py:47-63`).

**Fix:** Either implement explicit capability/status v1 translators and provider payloads, or add both methods to the controlled deprecated surface so the routes return `unsupported_feature`/501. Add ASGI regression tests for every still-mounted route, including these two.

### CR-03: The public in-process conformance and timeout guarantees no longer execute their provider calls — **BLOCKER**

**File:** `src/totem/hardware/hosts/in_process.py:186-190`

**Issue:** In-process requests now always call the worker's provider-owned `dispatch` SPI. The public `InProcessDriverHost` constructor still accepts the legacy `write_frame`-only provider used by the conformance and cooperative-timeout contracts, so `_dispatch` immediately returns `invalid_request` instead of invoking it. This deterministically fails `test_public_conformance_runner_keeps_case_order_and_empty_lifecycle` and makes both deadline tests report no timeout (`tests/unit/hardware_runtime/test_in_process_host.py:74-106`). Consequently the asserted cancellation, contamination, and held-lease behavior is no longer exercised, and the full local safe suite is red.

**Fix:** Make the conformance/timeout fixtures implement the required provider-owned `dispatch` SPI (including cancellation propagation), or retain a deliberately versioned compatibility adapter until those test providers are migrated. In either case, restore passing conformance and cooperative/uncooperative deadline tests before release.

---

_Reviewed: 2026-08-27T19:19:05Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
