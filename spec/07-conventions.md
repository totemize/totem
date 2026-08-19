# 07 — Protocol Conventions

Status: Draft

The single home for Totem's interop values: everything a totem implementer
MUST honor that isn't already defined by the referenced NIPs. Behavioral
requirements live in their own documents (relay: `04-relay.md`, net code:
`03-network.md`); this file only pins values. Values marked **TBD** are
decided during this design phase (see `README.md` rules).

## Port registry

Once a client can reach a totem by any means, it knows where the services
live.

| Service | Port | Notes |
|---------|------|-------|
| Relay (websocket + NIP-11 HTTP) | **TBD** | Standard nostr relay port |
| Web app (owner control / guest info) | **TBD** | HTTP |

A totem MUST serve both on the ports registered here, on every on-ramp.

## AP network conventions

- **SSID: `!Totem`**, the same on every totem, open security. Same SSID +
  unique BSSIDs form one standard ESS: guests save the network once and
  roam between all totems natively (the Freifunk model). The leading `!`
  sorts the network to the top of alphabetically ordered pickers. Open
  security is required for uniformity: clients key a saved network on SSID
  *plus security type*, so one totem using a PSK would break roaming for
  all. All real security is layered above: FIPS Noise IK authenticates
  peer links, the challenge protocol (`02-identity.md`) authenticates
  totem claims, and relay policy governs what guests may write.
- A roaming totem seeing `!Totem` treats it as a totem beacon (hint only —
  identity is proven by the handshake and challenge, never by the name).
- **Identical AP subnet on every totem**, so a roaming client keeps its
  DHCP lease across totems. The totem MUST be reachable at its AP's
  **gateway address** (and/or an fd00 ULA — **TBD**) so guests never guess
  where the totem is.
- A captive portal landing on the web app is **TBD** (open question).

## NIP-11 totem marker

The relay's NIP-11 info document MUST include a **totem marker**: a boolean
field (name **TBD**) that is `true` when the host is a totem.

The marker is the recognition *hint*; authentication is the challenge in
`02-identity.md`. A missing marker or `false` means "not a totem".

## Challenge protocol

Values for the recognition challenge (`02-identity.md`):

- Endpoint path: **TBD** (placeholder `/totem/challenge`).
- Challenge event kind: **TBD** — NIP-98's 27235 with an added `nonce` tag,
  or a NIP-01 ephemeral kind (20000–29999).
- Freshness window for `created_at`: **TBD**.

## Key encoding

Public keys on the wire are **hex**, per NIP-01. Bech32 (`npub`/`nsec`) is
the human-facing encoding and MUST NOT be required by wire formats.

## Transport

v1 uses plain `http://` and `ws://`. The AP network has no DNS to name
certificates, and TLS/mixed-content restrictions would break real mobile
clients. Transport confidentiality is provided by the fabric where it exists
(FIPS links are encrypted) and by nostr's end-to-end event signatures; the
content itself is public-by-design relay data.

## Sync

Totem-to-totem sync is **plain NIP-77 negentropy** between relays, with event
transfer over the same websocket. There is no Totem-specific sync profile —
no totem-defined filters, direction rules, or limits. Relay requirements are
defined in `04-relay.md`.
