---
phase: HW-01-capability-oriented-hardware-runtime
plan: "25"
subsystem: screen-hardware-boundary
tags: [python, screen, ports, canonical-bus, nip-5d, compatibility, pytest]
requires:
  - phase: HW-01-24
    provides: Loopback-only canonical bus, redacted runtime health, and opaque capability dispatch.
provides:
  - Narrow screen FrameSink, HardwareHealth, and PowerStatus contracts.
  - Raw frame, readiness, and power translation through correlated canonical bus messages.
  - A compatibility-named display client and unchanged screen CLI/geometry/systemd behavior without manager ownership.
affects: [HW-01-26, HW-01-32, screen, hardware-api, compatibility]
tech-stack:
  added: []
  patterns:
    - Screen renderers depend on narrow async ports; the bus adapter is the sole hardware transport translation.
    - Binary frame data remains raw and checksummed inside the existing canonical carrier rather than entering JSON/base64 routes.
key-files:
  created:
    - src/totem/screen/ports.py
    - src/totem/screen/adapters/__init__.py
    - src/totem/screen/adapters/hardware_bus.py
  modified:
    - src/totem/screen/controller.py
    - src/totem/screen/display.py
    - src/totem/screen/readiness.py
    - src/totem/screen/__main__.py
    - src/totem/hardware/api/bus.py
    - tests/unit/test_screen.py
    - tests/unit/test_hardware_bus.py
key-decisions:
  - "Screen owns rendering, boot progression, and systemd notification; it sees only frame, health, and optional power port values."
  - "Frame uploads use the canonical THW1 raw-attachment carrier with an octet-stream descriptor, not the retired base64 route."
  - "Canonical hardware.status.get returns only ready/degraded status so screen readiness never imports runtime health models or calls /health."
metrics:
  duration: 4m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 25: Screen Capability-Bus Boundary Summary

**The screen is now a narrow-port application client that renders and boots independently while sending raw frames and receiving readiness only through the loopback canonical hardware bus.**

## Performance

- **Duration:** 4m
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments

- Defined `FrameSink`, `HardwareHealth`, and `PowerStatus` screen-domain protocols with immutable, presentation-safe health and power values.
- Added `HardwareBusScreenAdapter`, which maintains the prior shared urllib connection pool and timeout/retry cadence while validating request/result correlation and stable failures.
- Converted frames to bounded monochrome raw attachments sent as `display.frame.write`; no screen code serializes a PNG or base64 image.
- Added canonical `hardware.status.get` redacted readiness projection and routed optional `power.telemetry.read` through opaque runtime handles.
- Preserved `DeviceManagerDisplay` as an import-compatible facade, `totem-screen` commands/flags/environment geometry inputs, boot splash progression, rotation, synthetic replay, and systemd notification.

## Task Commits

1. **Task 1 RED: Specify screen bus ports** — `4cbc315` (`test`)
2. **Task 1 GREEN: Define screen-domain ports and canonical adapter** — `3aa0f6a` (`feat`)
3. **Task 2 RED: Specify compatibility and entry-point behavior** — `f706b3b` (`test`)
4. **Task 2 GREEN: Rewire screen boot through ports** — `1023a92` (`feat`)

## Verification

- `.venv/bin/python -m pytest tests/unit/test_screen.py -x` — passed (12 tests).
- `.venv/bin/python -m pytest tests/unit/test_hardware_bus.py -x` — passed (4 tests).
- `.venv/bin/python -m pytest tests/unit/test_screen.py tests/unit/test_hardware_bus.py -x` — passed (16 tests).
- `.venv/bin/python -m compileall -q src/totem/screen src/totem/hardware/api` and `git diff --check` — passed.
- Source-boundary scan found no screen imports of managers, devices, built-in providers, SPI/GPIO drivers, direct `/health` or `/display/image` routes, or base64 frame encoding.
- All verification used local fake ports, a mocked urllib opener, and in-process ASGI coverage only. No SSH, network service, deployment, device, radio, USB/serial/I2C/GPIO, or hardware-marked test was contacted.

## Decisions Made

- Keep `DeviceManagerDisplay` as a direct subclass compatibility facade rather than emitting a deprecation warning or changing callers.
- Make `HardwareBusScreenAdapter.health` and `.power` distinct port objects, since both domain ports naturally expose `snapshot()` but return different screen-owned values.
- Add a bounded `hardware.status.get` canonical message because a screen client cannot retain the prohibited legacy `/health` request while still polling readiness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added canonical status and power dispatch support to the bus**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** The existing canonical bus supported only `display.frame.write`, leaving no bus-only readiness path after removing the prohibited direct `/health` client request.
- **Fix:** Added redacted `hardware.status.get` projection and `power.telemetry.read` capability mapping through existing opaque handles, with local bus coverage.
- **Files modified:** `src/totem/hardware/api/bus.py`, `tests/unit/test_hardware_bus.py`.
- **Commit:** `3aa0f6a`.

**Total deviations:** 1 auto-fixed (Rule 2 missing critical functionality). **Impact:** Completes the planned canonical-bus-only boundary without exposing runtime/provider objects or adding a parallel owner.

## Known Stubs

None.

## Threat Flags

None — the planned frame/status boundary validates carrier bounds, media descriptors, request/result correlation, loopback routing, and redacted stable screen values.

## TDD Gate Compliance

- RED `4cbc315` failed during collection because the new adapter package did not exist.
- GREEN `3aa0f6a` implemented the ports and adapter; focused screen and bus tests passed.
- RED `f706b3b` failed because the compatibility facade still used legacy route ownership.
- GREEN `1023a92` rewired the facade and entry point; the full local screen suite passed.

## Next Phase Readiness

- Later application facades can follow the same narrow-port/canonical-bus translation pattern without importing providers or creating another runtime.
- API-04's whole-surface compatibility regression remains owned by Plan 01-32; this plan preserves the screen portion.

## Self-Check: PASSED

- Found every declared screen port, adapter, compatibility, readiness, entry-point, bus, and test file on disk.
- Found task commits `4cbc315`, `3aa0f6a`, `f706b3b`, and `1023a92` in git history.
