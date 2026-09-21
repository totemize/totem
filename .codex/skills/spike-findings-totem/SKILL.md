---
name: spike-findings-totem
description: Implementation blueprint from spike experiments. Requirements, proven patterns, and verified knowledge for building Totem's capability-oriented Python hardware runtime. Auto-loaded during implementation work.
---

<context>
## Project: totem

Totem's complete Python hardware subsystem is moving from device-type managers
and model-specific branches to an extensible runtime built from hardware facts,
versioned capabilities, independently released driver providers, deterministic
resolution, explicit resource leases, and configurable process or in-process
hosts. Existing interfaces remain migration facades, and `screen` stays a
bounded application that consumes narrow hardware ports.

Spike sessions wrapped: 2026-08-22
</context>

<requirements>
## Requirements

- Physical models and SKUs are data (`HardwareFacts` and optional profiles),
  never branches in a closed class hierarchy.
- Stable, independently versioned capabilities are the application-facing
  abstraction; concrete drivers are replaceable providers.
- Third-party drivers are independently installable Python distributions and
  do not require edits to a core registry or manager factory.
- Driver execution is process-isolated by default. Global and per-plugin
  configuration may explicitly opt into in-process execution.
- Both host modes implement the same transport-neutral, NIP-5D-shaped logical
  contract used by Totem's control plane: typed JSON-object semantics,
  request/result correlation by `id`, `.result` response types, structured
  errors, and unsolicited typed events.
- “Same host contract” means functional envelope parity, not identical fault
  containment. Process hosts support hard termination/restart; in-process
  cancellation is cooperative and native failures remain daemon-wide.
- After an uncooperative in-process timeout, the binding is contaminated, new
  work is rejected, and resource leases remain held until a controlled daemon
  restart. The runtime must never pretend the timed-out thread was stopped.
- Carrier encodings are replaceable and must not use executable
  serialization such as pickle. Binary attachments are bounded and explicit.
- Every carrier preserves a strict JSON-compatible logical value model;
  codec-only types may not leak into capability contracts. Protocol and codec
  versions are explicit and unsupported values fail before payload dispatch.
- Unknown unsolicited types are ignored for NIP-5D forward compatibility;
  unknown ID-bearing requests receive a correlated structured error, matching
  Totem's existing control-plane behavior.
- Isolation covers all Python hardware capabilities, including display,
  power, storage, NFC, Wi-Fi, and Bluetooth; it is not a screen-only design.
- `screen` remains a bounded application context and consumes narrow display,
  power, and health ports from the hardware runtime.
- Existing imports, commands, routes, environment variables, and systemd
  units remain available through migration facades.
- No bench device is used by these local spikes. Pi-class startup, memory,
  latency, and frame-transfer acceptance remains an explicit follow-up gate.
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Process topology | `references/process-topology.md` | Use one isolated process per provider by default, with per-binding grouping as an explicit smaller-blast-radius override pending Pi PSS validation. |
| Driver IPC | `references/driver-ipc.md` | Use NIP-5D-shaped canonical JSON control frames plus bounded, checksummed raw attachments; reserve MessagePack without making it a v1 dependency. |
| Dual-host lifecycle | `references/dual-host-lifecycle.md` | Share functional envelopes and conformance tests, while keeping timeout, crash, restart, and lease-release guarantees explicitly host-specific. |

## Source Files

Original spike READMEs, harnesses, configurations, and result evidence are
preserved in `sources/`. Shared executable fixtures are in `sources/_support/`.
</findings_index>

<metadata>
## Processed Spikes

- 001-a-per-binding-isolation
- 001-b-per-provider-isolation
- 002-a-nip5d-framed-json
- 002-b-nip5d-messagepack
- 003-dual-host-contract
</metadata>
