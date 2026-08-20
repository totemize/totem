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
  a totem appears, and it renders in nostr clients' relay lists. The suffix
  is derived from the latest valid device-authored kind-0 `name`, falling
  back to `device.name` configuration and finally `Totem`; strfry hot-reloads
  the derived value without a relay restart.
- **`pubkey` MUST be the device npub** (hex or bech32) — the identity
  claim the challenge verifies (`02-identity.md`). `pubkey` is NIP-11's
  administrative-contact field, present in every strfry build; Totem uses it
  as the relay/device identity claim, not as owner authorization
  (`02-identity.md`). A relay MAY additionally set `self` to
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

## Owner HTTP API

The public web listener exposes these same-origin JSON endpoints:

| Method | Path | Access |
|--------|------|--------|
| `POST` | `/api/auth/challenge` | Public; binds a one-use nonce to one supported mutation URL, method, and body hash |
| `GET` | `/api/owner` | Public claimed/unclaimed boolean; never exposes the owner key |
| `POST` | `/api/owner/claim` | Signed; first valid signer claims an unclaimed device |
| `GET` / `PUT` | `/api/metadata` | Public read; owner-authenticated kind-0 publication |
| `GET` / `PUT` | `/api/config` | Public effective-policy read; owner-authenticated policy override |

Mutation authorization is kind 27235 with exact `nonce`, `u`, `method`, and
`payload` tags. The nonce is single-use and replaces wall-clock freshness;
the payload is SHA-256 of the exact request body. The event signer MUST equal
the stored owner after claim.

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
| `totem.events.get` | request | oldest-first bounded history of pushes from the current daemon run |
| `totem.contacts.add` / `totem.contacts.remove` | request | npub — the single-writer path for kind 3 updates |
| `totem.peer.seen` | push | fips authenticated a peer |
| `totem.peer.gone` | push | peer left the mesh (last authenticated npub) |
| `totem.peer.candidate` | push | NIP-11 marker + npub claim matched; signed challenge still pending |
| `totem.recognized` | push | signed challenge verdict passed (peer is a totem) |
| `totem.befriended` | push | kind 3 published |
| `totem.sync.started` / `totem.sync.done` | push | npub, encounter, periodic attempt, direction; done adds outcome, duration, exit/error, and event counts when the relay runner exposes them reliably |
| `totem.owner.claimed` | push | the previously unclaimed device persisted its owner |
| `totem.metadata.changed` | push | device-signed kind-0 event ID and effective name |
| `totem.config.changed` | push | newly persisted effective engagement policy |

Pushes are lossy by design: consumers reconcile against `totem.status.get`
on (re)connect. `totem.events.get` is operator-facing recent history, bounded
to the current process; it does not make push delivery reliable. The CLI
(`totemctl`) is a client of this bus and introduces
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
