---
spike: 002a
name: nip5d-framed-json
type: comparison
validates: "Given NIP-5D-shaped control envelopes and binary display frames, when carried over a Unix-domain byte stream as bounded framed JSON with explicit raw attachments, then request/result correlation, pushes, fragmentation, pipelining, integrity checks, and rejection paths remain deterministic."
verdict: PARTIAL
related: [002b, 003]
tags: [ipc, nip-5d, json, unix-socket, attachments]
---

# Spike 002a: NIP-5D framed JSON

## What This Validates

Given NIP-5D-shaped control envelopes and binary display frames, when carried
over a Unix-domain byte stream as bounded framed JSON with explicit raw
attachments, then request/result correlation, pushes, fragmentation,
pipelining, integrity checks, and rejection paths remain deterministic.

## Research

The current [NIP-5D draft](https://github.com/nostr-protocol/nips/pull/2303)
defines a generic JSON object with a `domain.action`-style `type` discriminator
and requires unknown types to be silently ignored for forward compatibility.
It deliberately leaves domain messages to capability specifications. Totem's
existing `totemd` bus specializes that pattern: requests carry `id`; results
use the request type plus `.result`, echo `id`, and carry `ok`; typed pushes
have no correlation ID. Its dispatcher also returns a correlated error for an
unknown request. This spike preserves both rules by ignoring an unknown
uncorrelated push and answering an unknown ID-bearing request with an error.

Python's [`socket` documentation](https://docs.python.org/3.9/library/socket.html)
exposes `AF_UNIX` streams and distinguishes `sendall`, which completes the
byte send or raises, from `send`, whose caller must handle partial writes. The
[`struct` documentation](https://docs.python.org/3.9/library/struct.html)
recommends explicit byte order and sizes for cross-process data. The carrier
therefore uses a fixed 16-byte network-order prefix and a receive-exact loop;
it never assumes one `recv` equals one message.

| Approach | Advantages | Costs | Status |
|----------|------------|-------|--------|
| Newline-delimited JSON | Human-readable and trivial | No safe raw binary boundary; line and size handling becomes ad hoc | Rejected |
| Length-framed JSON plus raw attachments | Reuses Totem semantics; inspectable control plane; bounded binary without base64 | Small custom framing layer | Chosen for 002a |
| JSON with inline base64 | One JSON value | Expands binary and creates encoding copies | Measured, not chosen |
| HTTP request + SSE push | Already used by `totemd`; excellent service boundary | Heavier child-host dependency and split request/push carriers | Kept for the daemon bus, not the driver carrier |

### Experimental carrier

```text
16-byte prefix (!4sBBHII)
  magic = THW1
  protocol version = 1
  header codec = 1 (canonical JSON)
  flags = 0
  header byte length (bounded to 64 KiB)
  total attachment byte length (bounded to 16 MiB)
JSON envelope with reserved _attachments descriptors
raw attachment bytes concatenated in descriptor order
```

Every descriptor contains an ID, media type, length, and SHA-256 digest. IDs
must be unique, every payload byte must be claimed, and the digest is verified
before dispatch. The supervisor will establish plugin identity through the
spawned process/session and socket permissions; identity is not accepted from
an untrusted message field.

## How to Run

From the repository root:

```bash
python3 .planning/spikes/002-a-nip5d-framed-json/run.py
```

The command runs conformance and microbenchmark cases and writes
`results.json`.

## What to Expect

- A real `AF_UNIX` socket-pair conversation exercises display request,
  correlated result, typed completion push, ignored unknown push, correlated
  unknown-request error, and a `totem.status.get` compatibility fixture.
- Fragmented and pipelined frames decode correctly.
- Truncation, invalid magic, codec mismatch, oversized declared lengths,
  duplicate attachment IDs, missing types, reserved fields, and checksum
  damage fail with stable protocol error codes.
- A 250×122 monochrome frame travels as 3,813 raw bytes rather than base64.

## Observability

`results.json` records the protocol limits, every named conformance check,
platform/runtime versions, frame sizes, and seven-sample median decode cost for
control and display frames.

## Investigation Trail

1. Treated NIP-5D as the logical-envelope source, not as a Unix framing spec;
   its normative transport is browser `postMessage`.
2. Preserved `totemd`'s `.result`/`id`/`ok` convention and reconciled its
   unknown-request error with NIP-5D's forward-compatibility rule by applying
   silent ignore only to unsolicited messages.
3. Separated carrier metadata from capability payload using one reserved
   `_attachments` field and fixed prefix bounds.
4. Added adversarial receive cases before benchmarking so a fast happy path
   cannot validate an unsafe parser.
5. Canonically sorted attachment IDs and proved differently ordered input
   mappings produce identical wire bytes. This keeps raw payload ordering from
   becoming an accidental language/runtime behavior.

## Results

**PARTIAL, with the carrier behavior validated locally.** All 22 checks passed,
including a real Unix-domain socket conversation, one-byte reads, two
pipelined frames, multiple checksummed attachments, canonical attachment
ordering, invalid type/ID/reserved fields, truncation, oversized declarations,
bad magic/version/flags/codec, malformed JSON, checksum damage, duplicate IDs,
unclaimed bytes, and a capability-level missing-attachment error.

The representative 250×122 monochrome display message occupied 4,132 bytes:
16 prefix bytes, 303 JSON header bytes, and 3,813 raw frame bytes. Inline
base64 occupied 5,240 bytes, so explicit raw attachment framing saved 1,108
bytes for the complete message. On this macOS/Python 3.9 run, seven-sample
median decode cost was 3.090396 µs for the control request and 6.8475 µs for
the display frame; encode-plus-decode was 5.695792/12.946834 µs.

The experiment validates the semantics, bounds, and parser behavior, not a
production implementation or Pi budget. Its final comparison verdict waits
for 002b and the Pi-class run. JSON retains an important maintenance advantage:
operators can inspect the same message vocabulary already exposed by `totemd`
without a special decoder.
