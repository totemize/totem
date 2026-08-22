# Phase 1 ASVS Level 1 traceability

This matrix is planning evidence for the Phase 1 trust boundaries. It does not claim that a later security audit substitutes for implementation tests. ASVS references are area-level control identifiers because the phase is a local hardware runtime rather than an end-user authentication application; the concrete test in every applicable row is the acceptance gate.

## Applicable controls

<a id="sec-01"></a>
### SEC-01 — Untrusted manifests and typed configuration

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V1 Architecture, V5 Validation, V10 Malicious Code, V14 Configuration | Installed package metadata or TOML selects code/resources before validation, or a manifest imports provider code. | 01-02 Task 1 packages/tests the public contract and fixture sentinel; 01-03 Task 1 validates catalog metadata before child import; 01-05 Task 1 parses typed precedence and rejects only the affected binding. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_public_api_fixture.py tests/unit/hardware_runtime/test_catalog_claim_tracer.py tests/unit/hardware_runtime/test_config.py -k 'manifest or before_import or api_major' -x` |

Required assertions: import-free distribution-file lookup; bounded/schema-validated fields; explicit binding &gt; plugin &gt; global &gt; manifest precedence; unknown keys/types are actionable; provider import occurs only after resolve/claim in the selected host.

<a id="sec-02"></a>
### SEC-02 — Secrets and inherited descriptors

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V5 Validation, V7 Error Handling, V8 Data Protection, V14 Configuration | Secret values enter manifests, logical IPC, diagnostics, SSE, logs, or benchmark output; inherited descriptors are confused with secret strings. | 01-05 Task 1 models credential/file refs and inherited descriptors; 01-23/24/26/32 redact projections and outward errors; 01-33 tests final output. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_config.py tests/unit/test_hardware_bus.py tests/unit/test_phase1_regression.py -k 'secret or credential or descriptor or redact' -x` |

Required assertions: secret-bearing config values are never serialized; descriptors use allowlisted parent-created attachment metadata; diagnostics identify the reference, not its contents; tracebacks/config dumps do not cross public boundaries.

<a id="sec-03"></a>
### SEC-03 — Loopback NIP-5D bus and SSE

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V4 Access Control, V5 Validation, V9 Communications, V13 API/Web Service | A broad legacy listener accidentally exposes the canonical control bus/SSE, permits origin/header bypass, or loses request/result correlation. | 01-24 Task 1 route-protects `POST /bus` and `GET /bus/events`; 01-26 translates existing REST/WebSocket traffic without making the canonical endpoints public. | `.venv/bin/python -m pytest tests/unit/test_hardware_bus.py tests/unit/test_api_facades.py -k 'loopback or sse or correlation or facade' -x` |

Required assertions: canonical endpoints accept loopback peers only, including proxied/header edge cases; request ID/type correlation is stable; SSE has typed projection, bounded/lossy queues, and no secret/internal traceback fields.

<a id="sec-04"></a>
### SEC-04 — Framed Unix carrier and raw attachments

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V5 Validation, V9 Communications, V12 Files/Resources, V13 API/Web Service | Fragmented, pipelined, truncated, oversized, count-mismatched, or identity-spoofed frames allocate unbounded memory or desynchronize sessions. | 01-08 Tasks 1–2 define logical correlation and `THW1` framed canonical JSON with raw attachment descriptors and parent-bound session identity. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -x` |

Required assertions: 64 KiB header, 16 MiB attachment total, 16 attachment maximum (or tighter capability limits); exact-length reads; EOF/trailing/unknown codec/type behavior; attachment offset/length/hash integrity; payload identity cannot override spawn identity.

<a id="sec-05"></a>
### SEC-05 — Filesystem and Unix-socket paths

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V5 Validation, V8 Data Protection, V12 Files/Resources, V14 Configuration | Traversal, symlink escape, unsafe socket placement/permissions, or reused stale paths cross configured resource scope. | 01-08 Task 2 owns Unix carrier path/lifecycle tests; 01-18 Task 1 normalizes relative storage paths beneath a leased root. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py tests/unit/hardware_runtime/test_builtin_storage.py -k 'socket or path or cleanup or traversal or symlink or root' -x` |

Required assertions: runtime-created socket directory/path and permissions; stale-path refusal/cleanup bound to the owning generation; relative normalized storage paths only; absolute/traversal/symlink escape rejected before file access.

<a id="sec-06"></a>
### SEC-06 — D-Bus, device resources, child privileges, and provider import boundary

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V1 Architecture, V4 Access Control, V10 Malicious Code, V12 Files/Resources, V14 Configuration | A provider receives undeclared D-Bus/device/filesystem resources, provider code enters the daemon, or subprocess isolation is represented as an OS sandbox. | 01-07 Task 1 normalizes/leases resources; 01-09 Task 2 spawns after claims; 01-11–22 providers declare exact resources; 01-32 preserves credential/resource service wiring. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_broker.py tests/unit/hardware_runtime/test_process_host.py tests/unit/hardware_runtime/test_builtin_wifi.py tests/unit/hardware_runtime/test_builtin_bluetooth.py -k 'resource or import or privilege or dbus' -x` |

Required assertions: daemon never imports a concrete provider; child receives only declared leases/descriptors/config; D-Bus service/adapter/interface names are bound to resolved facts and claims; mocks prove no system bus access; docs explicitly distinguish crash isolation from package/OS trust.

<a id="sec-07"></a>
### SEC-07 — Child crash, hang, cleanup, and lease release

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V7 Error Handling, V11 Business Logic, V12 Files/Resources | A crashed/hung child keeps serving, a replacement overlaps the old generation, or leases release before confirmed death. | 01-09 Task 2 implements deadline/cancel/terminate/kill/wait, confirmed-exit gating, generation isolation, backoff, and quarantine; 01-33 rechecks cleanup. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py tests/unit/test_phase1_regression.py -k 'crash or hang or death or lease or generation or cleanup' -x` |

Required assertions: no lease release/reassignment before positive death confirmation; stale results/events rejected by generation/session; bounded recovery; quarantine after configured failure window; no surviving child/socket/task after close.

<a id="sec-08"></a>
### SEC-08 — Configurable in-process trust boundary

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V1 Architecture, V4 Access Control, V7 Error Handling, V11 Business Logic | Administrator opt-in third-party code blocks cancellation or mutates daemon state while diagnostics falsely claim crash containment. | 01-10 Task 1 uses the identical DriverHost/logical transcript, cooperative cancellation, contamination state, retained leases, work rejection, and daemon-restart requirement. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py tests/unit/hardware_runtime/test_conformance.py -k 'contaminated or timeout or lease or restart' -x` |

Required assertions: process remains default; per-plugin/binding override is explicit; uncooperative in-process work becomes `CONTAMINATED`; new work is rejected; leases remain; health says restart required; no claim of crash containment.

<a id="sec-09"></a>
### SEC-09 — Errors, logs, events, and evidence integrity

| ASVS L1 areas | Risk | Mitigation owner | Local automated verification |
|---|---|---|---|
| V7 Error Handling, V8 Data Protection, V11 Business Logic | Diagnostics omit decisive evidence, leak internals/secrets, or mislabel controller evidence as hardware acceptance. | 01-06 evidence/diagnostics, 01-09 lifecycle events, 01-24 bus projection, facade plans 25–32, and 01-33 validation/benchmark gate. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py tests/unit/hardware_runtime/test_lifecycle.py tests/unit/test_phase1_regression.py -k 'evidence or event or redact or acceptance' -x` |

Required assertions: stable public error codes; complete resolver support/missing/rejection evidence; typed lifecycle ordering; no tracebacks/secrets; benchmark records provenance/completeness and cannot mark incomplete or controller-only evidence accepted.

## Inapplicable ASVS L1 areas

| ASVS area | Phase disposition |
|---|---|
| V2 Authentication | No new end-user identity/authentication mechanism is introduced. The canonical hardware bus is a loopback-only daemon boundary (SEC-03); preservation of any existing public application authentication remains outside this hardware-ontology phase. |
| V3 Session Management | The hardware logical protocol uses request correlation and parent-created provider sessions, not browser/login sessions or authentication tokens. Correlation/session-spoofing controls are covered by SEC-03/04. |
| V6 Stored Cryptography | The phase stores no new cryptographic key or encrypted record. Optional attachment hashes are integrity checks, not authentication; credential material remains inherited/referenced under SEC-02. |

## High-severity gate

Every high/critical risk above has a mitigating implementation task and local automated test. A plan must stop on a failing mapped test; a later `gsd-secure-phase` audit is additive review, not substitute evidence. Pi hardware and deployed-default acceptance remain manual deferred gates and cannot green any ASVS row from controller-only execution.
