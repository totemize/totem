# 11 — Myco Integration and Totem Napplet

Status: Draft

Totem has two deliberately separate Myco-facing artifacts:

1. The **Myco integration** is a native, headless service on a Totem. It lets
   the Totem pair with Myco devices and exchange files using Myco's protocol.
2. A **Totem napplet** is an ordinary shareable file. Myco can carry it, but
   does not execute it or grant it network access. A NIP-5D runtime executes
   the napplet and mediates its capabilities.

Neither artifact is an nsite, and installing the native integration MUST NOT
implicitly install, publish, or execute the napplet.

## Native integration

The reference implementation is `integrations/myco`. It is wire-compatible
with Myco commit `852bcda8cd0ccc2b604588c9b33c98e2523cea5b`, including:

- `myco://pair/<base64url(JSON)>` payloads carrying `{v,npub,name,secret}`;
- signed device events of kinds 9101, 9102, and 9103 on the pairing endpoint;
- NIP-17 messages inside NIP-59 gift wraps for file control;
- TTL-zero Myco `MESH` envelopes on the peer file-control WebSocket;
- XChaCha20-Poly1305 encrypted file packages and NIP-44 wrapped file keys; and
- SHA-256-addressed encrypted blobs fetched from the sending peer.

The integration MUST reuse the Totem's existing FIPS node, route, and device
identity. It MUST NOT start a second mesh node. The device secret MUST enter
through a protected service credential and MUST NOT be copied into mutable
integration state.

Pairing is always mutual. A request does not add either peer to the Circle;
one side explicitly accepts, then the signed acceptance completes the other
side. File offers likewise require explicit acceptance before encrypted bytes
are downloaded and decrypted.

The limits follow the compatible Myco release: 64 MiB plaintext, 64 tracked
transfers, ten-minute offers, and refusal of installable/app payloads. The
file-control and blob listeners MUST reject sources outside the local Circle.
The loopback operator API is not a mesh or guest interface. Port allocations
live in `07-conventions.md`.

### Optional radio lanes

The native integration MAY use the policy-free radio operations supplied by
the device manager, but it MUST preserve the ownership boundary:

1. For LE L2CAP CoC, the integration supplies an observed Bluetooth address
   and assigned PSM to the device manager. On connection, the device manager
   passes the descriptor directly to the fixed FIPS receiver with
   `SCM_RIGHTS`. Myco MUST NOT read or frame the CoC payload.
2. For Wi-Fi Aware, the integration publishes the fixed service name
   `myco.fips.v1` with empty passive service data. After a match, it exchanges
   the Android-compatible UTF-8 `<npub>|<port>` follow-up, validates the npub
   shape and non-zero port, and binds the result to that match. Once a data
   path yields a scoped peer IPv6 address, the integration submits `(peer
   npub, scoped UDP endpoint)` through the existing group-scoped FIPS control
   socket.
3. LAN and `!FIPS` SoftAP endpoints use that same FIPS UDP-connect operation.
   They are not alternate unauthenticated Myco application endpoints.

In every case, the pairing, relay, and encrypted-blob clients continue to use
the peer's stable FIPS mesh address. FIPS owns Noise identity, framing,
routing, selection among usable links, and fallback. The device manager owns
only the bounded radio resources that it creates. The Myco integration records
which lane it requested, but does not promote that observation into trust.
An operator-supplied or follow-up-discovered npub is only a dial hint: FIPS
MUST authenticate it through Noise and enforce its peer ACL. Myco pairing and
Circle membership remain separate, explicit state transitions.

The radio adapter MUST call the device manager over an explicit loopback URL
and FIPS through `/run/fips/control.sock`; it MUST NOT receive additional
Linux capabilities, sudo rules, a copied key, or access to radio payload
bytes. A failed optional lane leaves the existing FIPS-TUN path intact.

At the current implementation boundary, Linux NAN data-path creation reports a
typed unsupported result until a production NDP backend is available, and CoC
handoff requires the separate FIPS receiver implementation. Automatic Android
Aware identity follow-up messaging is implemented against the pinned Android
and upstream `iw` wire contracts, but real handset interoperability remains a
hardware-backed completion gate; the operator must not infer it from mock
follow-up or data-path success.

## Totem Nearby napplet

The reference napplet is `napplets/totem-nearby`. Its production payload is a
single self-contained `dist/index.html`, so the native Myco integration can
send it like any other file within the limits above.

The napplet MUST remain inside the NIP-5D sandbox. It MUST use a host-shell
capability such as ContextVM for discovery and tool calls; it MUST NOT open a
direct HTTP, WebSocket, or relay connection, access private keys, or treat a
received HTML file as trusted native code. Receiving the file does not replace
the NIP-5D runtime or its ACL/payment prompts.

A runtime that wants the napplet to operate a Totem must expose that Totem as a
ContextVM/MCP service. The current v1 loopback bus remains plain
NIP-5D-shaped HTTP/SSE (`05-kernel.md`, `10-control-plane.md`); the
shell-to-bus ContextVM bridge is a deployment concern and is not supplied by
the Myco transport itself.
