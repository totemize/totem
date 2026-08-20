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
| Relay (websocket + NIP-11 HTTP) | **7777** | Standard nostr relay port |
| Web app (owner control / guest info) | **8080** | HTTP; also serves `/totem/challenge` |
| Totem bus | **8081** | Loopback only (`127.0.0.1` / `::1`); NIP-5D-shaped JSON + SSE |

A totem MUST serve these services on the registered ports on every on-ramp
(the bus remains loopback-only).

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

A totem's relay declares itself using **standard NIP-11 fields** — no
custom fields:

- **`name` MUST start with `!Totem`** (e.g. `!Totem Mara`). The prefix is
  the totem marker — the same string as the AP SSID, one marker everywhere
  a totem appears, and it renders in nostr clients' relay lists.
- **`pubkey` MUST be the device npub** (hex or bech32) — the identity
  claim the challenge verifies (`02-identity.md`). `pubkey` is NIP-11's
  administrative-contact field, present in every strfry build; on a totem
  the device npub *is* the administrative identity (one identity
  everywhere, `02-identity.md`). A relay MAY additionally set `self` to
  the same npub where supported — a prober MUST accept either field as
  the claim.

A relay whose `name` lacks the prefix is not a totem. The marker is the
recognition *hint*; authentication is the challenge in `02-identity.md`.
Because all fields are standard, any conforming configurable relay can
declare totemhood — no relay fork or proxying required.

## Challenge protocol

Values for the recognition challenge (`02-identity.md`):

- Endpoint: **`/totem/challenge` on the web-app port** (served by the
  control plane, `10-control-plane.md` — not the relay server).
- Challenge event kind: **27235** (NIP-98's) with an added `nonce` tag.
- `created_at` is signed but MUST NOT be used as an acceptance clock; the
  single-use 128-bit nonce provides freshness without RTC/NTP dependence.
- The endpoint is guest-reachable and every request costs a signature:
  implementations MUST rate-limit it and SHOULD permit a small legitimate
  arrival burst.

## Totem bus

The control plane (`10-control-plane.md`) exposes a message bus for
on-device services (display, sound, lights), the owner web app, and CLI
clients. Messages use the NIP-5D wire shape (`{ "type": "domain.action",
... }`, request/result correlated by `id`); unsolicited pushes ride an SSE
stream at `/bus/events`. The bus is bound to loopback only. The `totem.*`
domain registry:

| Type | Kind | Payload / result |
|------|------|------------------|
| `totem.status.get` | request | mesh state, peers, contacts, totems met, relay event count, storage |
| `totem.config.get` | request | effective operator engagement policy (read-only in v1) |
| `totem.peers.get` | request | current mesh peers plus cached probe grade, candidate's unsigned `nip11_name` hint, and per-encounter recognition |
| `totem.contacts.add` / `totem.contacts.remove` | request | npub — the single-writer path for kind 3 updates |
| `totem.peer.seen` | push | fips authenticated a peer |
| `totem.peer.gone` | push | peer left the mesh (last authenticated npub) |
| `totem.peer.candidate` | push | NIP-11 marker + npub claim matched; signed challenge still pending |
| `totem.recognized` | push | signed challenge verdict passed (peer is a totem) |
| `totem.befriended` | push | kind 3 published |
| `totem.sync.started` / `totem.sync.done` | push | peer, direction, event counts |

Pushes are lossy by design: consumers reconcile against `totem.status.get`
on (re)connect. The CLI (`totemctl`) is a client of this bus and introduces
no separate API (`10-control-plane.md`).

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
