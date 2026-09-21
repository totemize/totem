---
phase: HW-01
fixed_at: 2026-08-27T20:55:00Z
review_path: .planning/phases/HW-01-capability-oriented-hardware-runtime/01-REVIEW.md
iteration: 3
findings_in_scope: 4
fixed: 2
skipped: 2
status: partial
---

# Phase HW-01: Code Review Fix Report

**Iteration:** 3

## Fixes Applied

### CR-06: Signed benchmark acceptance path

**Commit:** `2cdfe62`
**Applied fix:** Documented the controller-local trusted-allocation store and required CLI argument. Safe tests now create root device identities, signed HMAC records, both grouping records, and allocation/signature rejection cases.

### WR-01: Built-in child startup coverage

**Commit:** `13b7348`
**Applied fix:** Child startup validates a provider before `host.ready`; the built-in mock-transport process suite exercises display, NFC, Wi-Fi, Bluetooth, storage, and power without hardware access.

### Partial CR-03: Unrouteable generic legacy envelope

**Commit:** `aaea61f`
**Applied fix:** Removed `legacy_call`; retained compatibility operations use exact provider-owned v1 actions and unsupported historical operations return a controlled error. The final review found a separate public-conformance regression, listed below.

## Residual Blockers

### CR-01: Observed-inventory producer and empty-plan health

`13b7348` changed the template to consume controlled inventory, but the final review found no task/default/preflight that produces it and an empty plan still reports ready. Deployment must fail for missing inventory except an explicit `no_hardware` plan.

### CR-02: Capability/status routes bypass compatibility handling

The final review found `GET /network/capabilities` and `GET /network/status` call methods outside both translated and deprecated surfaces, causing HTTP 500. They need explicit v1 translators or controlled 501 deprecation plus ASGI coverage.

### CR-03: In-process provider-SPI conformance regression

The provider-owned dispatch migration leaves legacy `write_frame` test providers uncalled, so conformance and timeout guarantees no longer execute. Migrate those fixtures to the dispatch SPI (with cancellation) or add a versioned adapter.

## Verification Performed

- `tests/unit/test_radio_api.py`: 19 passed at the time of the CR-03 translation change.
- `tests/hardware/test_driver_host_bench.py -m 'not hardware'`: 6 passed, 1 hardware test deselected.
- `scripts/benchmark_driver_host.py --self-test`: passed; synthetic only.
- Built-in mock-transport suite: 42 passed.
- The final closure review found three deterministic failures in the full safe suite; phase status remains `issues_found`.

_Fixer: gsd-code-fixer_
_Iteration: 3_
