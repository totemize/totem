# Hardware Driver Runtime Contract

This document is the public contract for Totem's capability-oriented Python
hardware runtime.  It describes the boundary between applications, the runtime,
and independently packaged driver providers; it is not a device deployment
guide.

## Ownership and capability boundary

One `HardwareRuntime` owns an immutable resolved binding plan, its resource
broker, binding lifecycle records, hosts, health projection, and event stream
for one application lifespan.  An application receives opaque capability and
binding handles only.  Provider/driver objects, leases, owner tokens, concrete
models, and raw configuration never escape that runtime.

Hardware is described first as observed facts and optional data-only profiles.
The resolver selects a manifest-declared provider deterministically; ambiguous
automatic matches fail closed.  A provider can be independently distributed,
but its manifest is catalogued before its entry point may be imported.  Public
driver contracts depend on neither the runtime nor concrete drivers.

The `totem`, `totem-api`, and hardware ASGI application preserve their existing
command and route compatibility boundaries while composing one runtime.  Legacy
managers and device modules are client-only facades: they neither discover,
construct, own, nor close providers or runtimes.

## Logical bus and carrier

Both host modes implement the same transport-neutral, **NIP-5D-shaped** logical
envelope.  The shape is deliberately compatible with Totem's control-plane
vocabulary, not a claim that this hardware carrier is a NIP specification:

- Messages are strict JSON objects with a typed `type` field.
- Requests carry `id`; their correlated result uses the `.result` type form
  and preserves that ID.  Errors are structured with stable public codes.
- Unknown unsolicited types are ignored for forward compatibility.  Unknown
  ID-bearing requests receive a correlated `unknown_type` error.
- Binary values are bounded raw attachments, never base64 payloads or pickle.

Carrier v1 is the 16-byte network-order `THW1` prefix followed by a canonical
UTF-8 JSON header and ordered raw attachments.  Protocol version 1 and codec 1
(canonical JSON) are implemented.  Codec 2 is reserved and rejected.  Headers
are limited to 64 KiB, total attachments to 16 MiB, and attachment count to 16.
Descriptors are ordered by ID and cover exact byte lengths, media types, and
SHA-256 checksums before capability dispatch.

Canonical JSON is the current default, but its fleet suitability remains
provisional until allocated Pi measurements cover the documented workload.

## Hosting, grouping, and lifecycle

`process` hosting is the default.  `in_process` is an explicit controlled-start
override with binding > plugin > global > manifest precedence.  Host selection
and process grouping are separate: provider identity/version is the default
process group, while a manifest may request a per-binding group.

The parent publishes a binding only after resource claims and the generation-
bound `host.ready` handshake.  Each result is generation-checked.  On a process
crash or timeout the safety sequence is invalidate correlations, terminate,
kill if necessary, confirm exit, close the carrier, release leases, then start
a replacement generation under bounded retry/quarantine rules.  Leases are
never released merely because a child is presumed dead.

Lifecycle is explicit (`discovered` through `closed`) with required binding
readiness derived separately from optional degradation.  In-process calls keep
the same logical envelope, but timeout cancellation is cooperative.  A live,
uncooperative in-process invocation contaminates its binding group, rejects new
work, retains leases, and requires a controlled daemon restart; Totem never
claims to have killed a Python thread.

## Isolation boundary and security limits

Process isolation limits a faulty provider's Python failure domain.  It does
not make an installed package trusted, sandbox provider code, confer OS device
permissions, or replace systemd hardening, device-node policy, D-Bus identity,
or administrator package review.  Providers receive only bounded settings and
declared/brokered resources; secret values are represented by references and
must not appear in manifests, diagnostics, or benchmark records.

The loopback hardware bus trusts the ASGI peer address rather than forwarded
headers.  Its health/SSE projection is redacted and reports aggregate lossy
backpressure rather than provider objects or payloads.

## Acceptance status

Local unit, mock, API, carrier, lifecycle, and conformance evidence validates
the contract mechanics only.  It does **not** accept a Pi architecture or
authorize a deployed-default change.  The opt-in benchmark runbook in
[`hardware-driver-benchmark.md`](hardware-driver-benchmark.md) remains the
required gate for armv6l, armv7l, and aarch64.
