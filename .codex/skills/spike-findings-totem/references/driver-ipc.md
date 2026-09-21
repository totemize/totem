# Driver IPC

## Requirements

- Both host modes expose the same transport-neutral, NIP-5D-shaped logical
  contract: typed objects, request/result correlation by `id`, `.result`
  response types, structured errors, and unsolicited typed events.
- The logical value model is the strict JSON subset regardless of carrier.
- Binary values travel only as explicit, bounded attachments; executable
  serialization such as pickle is forbidden.
- Protocol and codec versions are explicit. Unsupported values fail before
  payload dispatch.
- Ignore unknown unsolicited messages for forward compatibility. Return a
  correlated structured error for an unknown ID-bearing request.

## How to Build It

1. Define capability messages as JSON-compatible schemas independently from
   the byte carrier. Reserve `type`, request `id`, result `ok`, result `error`,
   and carrier-owned `_attachments` consistently across capabilities.
2. Start carrier v1 with the tested 16-byte network-order prefix:

   ```python
   MAGIC = b"THW1"
   PROTOCOL_VERSION = 1
   PREFIX = struct.Struct("!4sBBHII")
   MAX_HEADER_BYTES = 64 * 1024
   MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
   MAX_ATTACHMENTS = 16
   ```

   The fields are magic, protocol version, codec ID, flags, JSON-header byte
   length, and total attachment byte length.
3. Use codec ID 1 for canonical UTF-8 JSON with sorted object keys and compact
   separators. Keep codec ID 2 reserved for the proven MessagePack variant,
   but do not require MessagePack in the v1 deployment.
4. Encode attachment descriptors in `_attachments`, sorted by attachment ID.
   Each descriptor contains `id`, `media_type`, `length`, and lowercase SHA-256.
   Concatenate the raw payloads in descriptor order after the header.
5. Enforce header and attachment limits immediately after reading the prefix,
   before allocating or reading declared payloads. Then verify descriptor
   shape, unique IDs, exact byte coverage, media types, and checksums before
   capability dispatch.
6. Implement stream reads with an exact-length loop and writes with `sendall`.
   Unix streams can fragment or pipeline frames arbitrarily:

   ```python
   def receive_exact(stream, size):
       chunks = []
       remaining = size
       while remaining:
           chunk = stream.recv(remaining)
           if not chunk:
               raise ProtocolError("unexpected_eof", "frame was truncated")
           chunks.append(chunk)
           remaining -= len(chunk)
       return b"".join(chunks)
   ```
7. Bind provider identity to the supervised spawn session and socket
   credentials. Never trust a provider identity copied from the payload.
8. Run one carrier conformance suite against every codec and both host modes.
   Preserve named cases for fragmentation, pipelining, malformed values,
   oversize declarations, version/codec mismatch, checksums, duplicate IDs,
   unclaimed bytes, correlation rules, and real Unix-socket exchange.

The dispatcher rule shared with `totemd` is:

```python
if request_id is None:
    return []  # unknown unsolicited push: ignore

return [(
    error_result(message, "unknown_type", f"unknown type: {message_type}"),
    {},
)]
```

## What to Avoid

- Do not use newline-delimited JSON once raw binary is required; its binary
  boundary and size accounting become ad hoc.
- Do not inline display frames as base64. The tested 3,813-byte monochrome
  frame made the full JSON message 1,108 bytes larger when inlined.
- Do not let MessagePack introduce bytes, extension values, non-string map
  keys, tuples, non-finite numbers, or wider integers into capability schemas.
- Do not assume one `recv()` call returns a whole prefix, header, or frame.
- Do not silently negotiate unsupported versions or codecs after decoding the
  payload.
- Do not expose plugin tracebacks as public structured errors; log internal
  details in the supervisor and return stable error codes.

## Constraints

- The tested bounds are a 64 KiB header, 16 MiB total attachment bytes, and 16
  attachments per frame. Production may tighten these per capability but must
  never leave them unbounded.
- Canonical JSON passed all 25 local conformance cases. The result is still
  `PARTIAL` until fleet CPU, latency, and real-frame transfer are measured.
- For a 250×122 monochrome frame, canonical JSON plus raw attachment used
  4,132 bytes. MessagePack used 4,085 bytes, a 47-byte total saving.
- `msgpack==1.1.2` was the newest tested version compatible with Python 3.9.
  Current 1.2.x requires Python 3.10, and no CPython 3.9 armv6/armv7 wheel was
  listed for the pinned release.
- The pure-Python MessagePack fallback passed conformance but decoded about
  2.5–3.7 times slower than standard-library JSON in the local comparison.

## Origin

Synthesized from spikes: 002a, 002b

Source files available in:
`sources/002-a-nip5d-framed-json/`,
`sources/002-b-nip5d-messagepack/`, and `sources/_support/`.
