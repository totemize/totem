---
phase: HW-01-capability-oriented-hardware-runtime
plan: "08"
subsystem: hardware-runtime
tags: [python, nip-5d, canonical-json, unix-socket, ipc, attachments]
requires:
  - phase: HW-01-04
    provides: Process-host tracer and shared bounded application/child carrier seam
provides:
  - Carrier-neutral strict JSON logical envelopes with safe correlated errors
  - Versioned THW1 canonical-JSON frames with checksummed raw attachments
  - Exact-read/sendall Unix stream adapter and adversarial protocol vectors
affects: [process-host, in-process-host, hardware-bus, driver-api, lifecycle]
tech-stack:
  added: []
  patterns: [NIP-5D-shaped logical values, THW1 bounded framing, generation-scoped correlation, raw attachment descriptors]
key-files:
  created:
    - src/totem/hardware/hosts/unix.py
    - tests/unit/hardware_runtime/test_protocol.py
  modified:
    - packages/totem-driver-api/src/totem_driver_api/messages.py
    - src/totem/hardware/hosts/protocol.py
    - src/totem/hardware/hosts/worker.py
    - src/totem/hardware/api/bus.py
    - tests/fixtures/hardware_runtime/protocol-vectors.json
    - tests/unit/hardware_runtime/test_runtime_tracer.py
key-decisions:
  - "Codec 1 is canonical UTF-8 JSON; codec 2 remains reserved and fails closed."
  - "Carrier identity remains parent/session-owned, while payload values are strict JSON and raw bytes travel only as descriptors."
  - "Correlation state is scoped to one host generation, so stale results cannot satisfy replacement-host requests."
patterns-established:
  - "Validate every prefix bound before body allocation/read, then validate header descriptors before payload dispatch."
  - "Use sendall and exact-length receive loops for all Unix driver frame transport."
requirements-completed: [ISO-03, ISO-04]
coverage:
  - id: D1
    description: Carrier-neutral strict JSON logical envelopes, structured errors, and generation-scoped request correlation.
    requirement: ISO-03
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_protocol.py
        status: pass
    human_judgment: false
  - id: D2
    description: Bounded THW1 canonical JSON frame codec and Unix stream transport with verified raw attachments.
    requirement: ISO-04
    verification:
      - kind: unit
        ref: tests/unit/hardware_runtime/test_protocol.py
        status: pass
      - kind: unit
        ref: tests/unit/hardware_runtime/test_runtime_tracer.py
        status: pass
    human_judgment: false
metrics:
  duration: 24m
  completed: 2026-08-26
status: complete
---

# Phase HW-01 Plan 08: Driver IPC Contract Summary

**Carrier-independent NIP-5D-shaped messages now use strict JSON values, generation-scoped correlation, and bounded THW1 Unix frames with checksummed raw attachments.**

## Accomplishments

- Added public logical messages, stable structured errors, strict recursive JSON normalization, attachment descriptors, and per-generation pending request tracking.
- Replaced the tracer-only length prefix with a 16-byte `THW1` prefix that rejects unsupported versions/codecs/flags and all oversized declarations before body reads.
- Added canonical UTF-8 JSON, duplicate-key/non-finite rejection, sorted attachment descriptors, exact integrity coverage, and `UnixFrameStream` exact-read/`sendall` transport.
- Promoted all 25 named framing spike cases into a production-independent fixture ledger, plus duplicate-key and non-finite-header coverage.
- Kept the prior process host and bus compatible while making their public error objects consistently structured and safe.

## Verification

- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -k 'logical or correlation or unknown' -x` — passed (15 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -x` — passed (35 tests).
- `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py tests/unit/hardware_runtime/test_runtime_tracer.py -x` — passed (37 tests).
- `.venv/bin/python -m compileall -q packages/totem-driver-api/src/totem_driver_api src/totem/hardware/hosts src/totem/hardware/api` — passed.
- `.venv/bin/python -m pytest tests/unit -x -q --tb=short` — passed (201 tests).

## TDD Gate Compliance

- RED `1ffb2a0` added the failing public logical-contract test and failed because the planned symbols were absent.
- GREEN `7481f0e` implemented logical envelopes, strict normalization, and generation-scoped correlation.
- RED `e368c84` added the failing frame/stream conformance tests and failed because the planned codec symbols were absent.
- GREEN `98cbfde` implemented the production frame codec and Unix transport; focused and full unit suites pass.

## Task Commits

1. **Task 1 RED: Freeze carrier-neutral logical envelopes and correlation rules** — `1ffb2a0` (`test`)
2. **Task 1 GREEN: Implement carrier-neutral logical envelopes and correlation rules** — `7481f0e` (`feat`)
3. **Task 2 RED: Enforce framed canonical JSON and raw-attachment integrity** — `e368c84` (`test`)
4. **Task 2 GREEN: Enforce framed canonical JSON and raw-attachment integrity** — `98cbfde` (`feat`)

## Files Created/Modified

- `packages/totem-driver-api/src/totem_driver_api/messages.py` — strict logical envelope, error, descriptor, and correlation contracts.
- `src/totem/hardware/hosts/protocol.py` — bounded canonical-JSON `THW1` codec and attachment integrity checks.
- `src/totem/hardware/hosts/unix.py` — stream adapter using exact reads and `sendall`.
- `tests/unit/hardware_runtime/test_protocol.py` — local conformance, fragmentation, pipelining, fault, and socketpair tests.
- `tests/fixtures/hardware_runtime/protocol-vectors.json` — 25 spike-equivalent behavior names plus production extension cases.

## Decisions Made

- Codec 1 is canonical UTF-8 JSON with sorted compact keys; reserved codec 2 is rejected rather than negotiated.
- Public messages do not carry provider identity; spawn/session routing remains outside caller-controlled payloads.
- Unknown uncorrelated pushes are ignored, while unknown ID-bearing requests receive one correlated `unknown_type` error.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Compatibility] Preserve decoded media metadata when re-framing an existing host request**
- **Found during:** Task 2
- **Issue:** A decoded attachment already carries carrier-owned media metadata; rejecting it during the next frame encode broke the existing process-host tracer.
- **Fix:** The codec validates and reuses matching media metadata when it re-frames decoded raw attachments.
- **Files modified:** `src/totem/hardware/hosts/protocol.py`
- **Verification:** Protocol and process-host tracer tests passed.
- **Committed in:** `98cbfde`

**2. [Rule 2 - Security] Complete public errors with safe stable messages**
- **Found during:** Task 2
- **Issue:** Existing worker and bus failures emitted code-only error objects, which no longer satisfied the shared structured-error contract.
- **Fix:** Added a small fixed public-message mapping; no exception details or tracebacks cross the host/bus boundary.
- **Files modified:** `src/totem/hardware/hosts/worker.py`, `src/totem/hardware/api/bus.py`, `tests/unit/hardware_runtime/test_runtime_tracer.py`
- **Verification:** Focused protocol/tracer suite and full 201-test unit suite passed.
- **Committed in:** `98cbfde`

**Total deviations:** 2 auto-fixed (1 Rule 1 compatibility, 1 Rule 2 security). **Impact:** Required compatibility and error-boundary hardening; no architecture expansion.

## Known Stubs

None.

## Issues Encountered

None after the in-scope compatibility correction.

## User Setup Required

None — local fixture-only verification requires no external service or device setup.

## Next Phase Readiness

Both hosts can now use a carrier-independent logical transcript with bounded Unix framing. Canonical JSON remains a provisional carrier candidate until the explicitly deferred Pi-class performance and real-frame acceptance evidence is captured.

## Self-Check: PASSED

- `messages.py`, `protocol.py`, `unix.py`, `test_protocol.py`, and `protocol-vectors.json` exist in the worktree.
- Task commits `1ffb2a0`, `7481f0e`, `e368c84`, and `98cbfde` exist in git history.
- No stub patterns were found in the plan-modified production files.
