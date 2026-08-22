---
spike: 002b
name: nip5d-messagepack
type: comparison
validates: "Given exactly the same NIP-5D-shaped envelopes, attachment framing, limits, and failure cases as 002a, when only the header codec changes to MessagePack, then its size and CPU gains can be compared with dependency, compatibility, deployment, and observability costs."
verdict: PARTIAL
related: [002a, 003]
tags: [ipc, nip-5d, messagepack, unix-socket, attachments]
---

# Spike 002b: NIP-5D MessagePack

## What This Validates

Given exactly the same NIP-5D-shaped envelopes, attachment framing, limits,
and failure cases as 002a, when only the header codec changes to MessagePack,
then its size and CPU gains can be compared with dependency, compatibility,
deployment, and observability costs.

## Research

The maintained [`msgpack` API](https://msgpack-python.readthedocs.io/en/stable/api.html)
provides one-shot `packb`/`unpackb`, separates strings from binary with
`use_bin_type=True` and `raw=False`, and defaults `strict_map_key=True` to
restrict map keys. The outer 64 KiB frame bound is enforced before decoding,
and decoder collection/string/binary limits are also set. MessagePack-only
values do not become part of the public contract: a recursive validator
rejects byte strings, extension types, non-string map keys, tuples, non-finite
numbers, excessive nesting, and integers outside signed 64-bit range. Both
codecs therefore expose the same JSON-compatible object model.

Dependency compatibility is the main surprise. Current `msgpack` 1.2.x
requires Python 3.10+, while Totem declares Python 3.9 support. The
[`msgpack` 1.1.2 release](https://pypi.org/project/msgpack/1.1.2/) is pinned for
this spike because it supports Python 3.9. Its published CPython 3.9 wheels
cover common x86-64 and aarch64 targets but do not list the fleet's armv6/armv7
artifact class, so source-build or pure-Python behavior must be verified on
those devices before adopting it.

| Approach | Advantages | Costs | Status |
|----------|------------|-------|--------|
| MessagePack header + raw attachments | Compact maps/strings; fast C implementation where a wheel exists | Extra dependency and decoder; opaque captures; Python/architecture matrix | Built in 002b |
| Canonical JSON header + raw attachments | Standard library; same readable vocabulary as `totemd`; universal install path | Larger/repeated field names; slower parser | Baseline from 002a |
| MessagePack-native binary values | Could eliminate attachment framing for small blobs | Changes logical semantics and weakens bounds/streaming clarity | Rejected |

The same 16-byte prefix uses codec ID 2. Attachments remain raw, explicit,
checksummed, and bounded; MessagePack encodes only the control header.

## How to Run

Create the ignored spike environment, install the pinned dependency, then run
the variant and paired comparison:

```bash
python3 -m venv .planning/spikes/.venv
.planning/spikes/.venv/bin/python -m pip install -r .planning/spikes/002-b-nip5d-messagepack/requirements.txt
.planning/spikes/.venv/bin/python .planning/spikes/002-b-nip5d-messagepack/run.py
.planning/spikes/.venv/bin/python .planning/spikes/002-b-nip5d-messagepack/compare.py
```

## What to Expect

- Native and pure-Python MessagePack pass the same named conformance checks as
  canonical JSON.
- `results.json` describes the standalone MessagePack run.
- `comparison.json` contains five order-rotated, three-codec trials and reports
  MessagePack/JSON ratios; below 1.0 means MessagePack was smaller or faster.
- The raw 3,813-byte display attachment is identical in both variants, so only
  the relatively small control header can shrink.

## Observability

Both outputs preserve codec/library versions, protocol limits, test names,
wire sizes, timing medians, and the unresolved Pi installation/performance
gate. A captured MessagePack header requires a decoder; this is an operational
cost, not merely an aesthetic difference.

## Investigation Trail

1. Reused the framing, dispatcher, message fixtures, limits, and all failure
   injection from 002a; codec ID and encode/decode functions are the only wire
   changes.
2. Added explicit JSON-subset validation so MessagePack cannot silently widen
   the public SPI to Python bytes, extension values, or arbitrary map keys.
3. Pinned the newest release compatible with Totem's Python 3.9 floor after
   current 1.2.x dropped that runtime.
4. Made the paired runner rotate codec order and compare multiple medians.
5. Added the package's pure-Python implementation as a deployment diagnostic,
   because armv6/armv7 lack a listed wheel. It must pass the same suite before
   its performance can be compared with the native extension and JSON.

## Results

**PARTIAL, and not selected as the v1 default codec.** Native MessagePack and
its pure-Python fallback passed the same 25 conformance cases as canonical
JSON. This proves the carrier can swap encodings without changing logical
requests, results, pushes, error handling, bounds, or attachment behavior.

Across five paired trials, MessagePack reduced the small control frame from 62
to 54 bytes (ratio 0.871) and the display frame from 4,132 to 4,085 bytes
(ratio 0.9886). The latter saves only 47 bytes because the 3,813 raw frame
bytes are identical. With the local native extension, decode time ratios were
0.8292 for control and 0.8724 for display; encode-plus-decode ratios were
0.7216/0.8011. Those are real local improvements but small absolute work.

The fallback diagnostic reverses the result: relative to standard-library
JSON it was 2.4939× slower for control decode and 3.7392× slower for display
decode; encode-plus-decode was 2.1915×/3.1897× slower. Combined with a Python
3.9-specific pin, no listed CPython armv6/armv7 wheel, opaque captures, and an
additional parser dependency, the modest native gain does not justify making
MessagePack the v1 default.

Keep the explicit codec field and reserve codec ID 2, but ship canonical JSON
unless a Pi-class run with the actual deployment artifact shows a material
budget violation. The verdict is `PARTIAL` because MessagePack is feasible and
semantically conformant, while its device install and performance path remains
untested rather than disproven.
