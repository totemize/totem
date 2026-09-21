# Spike Manifest

## Idea

Establish an extensible ontology and runtime boundary for Totem's complete
Python hardware subsystem. The design must support an open-ended set of
physical models, capability types, independently released drivers, and
compatibility combinations while preserving current interfaces during an
incremental migration from the PR #22 baseline.

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

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001a | Per-binding isolation | comparison | Given eight bindings, when each has its own child host, then one crash affects one binding and its resource cost is observable | PARTIAL | process, isolation, topology |
| 001b | Per-provider isolation | comparison | Given the same bindings, when one provider host multiplexes them, then cost falls while the larger failure domain is measurable | PARTIAL | process, isolation, topology |
| 002a | NIP-5D framed JSON | comparison | Given control envelopes and binary frames, when carried over a Unix socket as framed JSON plus bounded attachments, then requests, results, events, fragmentation, and rejection paths remain deterministic | PARTIAL | ipc, nip-5d, json, unix-socket |
| 002b | NIP-5D MessagePack | comparison | Given the identical logical envelopes and payloads, when only control encoding changes to MessagePack, then size and latency gains can be weighed against dependency and operability cost | PARTIAL | ipc, nip-5d, messagepack, unix-socket |
| 003 | Dual-host contract and failure parity | standard | Given one capability provider and conformance suite, when run in process and out of process, then functional outcomes match and containment differences are explicit | VALIDATED | host, conformance, lifecycle, isolation |

## Comparison Outcomes

- **Process granularity:** one process per provider distribution is the
  provisional default because it amortizes interpreter cost across bindings.
  Per-binding process grouping remains an explicit override for a smaller
  crash domain. Pi PSS and representative import measurements must lock this.
- **Carrier codec:** canonical JSON with bounded raw attachments is the
  provisional v1 default. MessagePack remains a reserved/negotiable codec, not
  a baseline dependency; its full display frame was only 47 bytes smaller and
  the un-wheeled pure-Python path was slower locally.
- **Host parity:** both modes share capability semantics and conformance tests.
  Only process mode promises hard termination, native-crash containment, and
  lease release after confirmed child death. In-process mode is an explicit
  trust/performance opt-in with cooperative cancellation.
