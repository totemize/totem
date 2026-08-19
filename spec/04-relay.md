# 04 — Relay Layer

Status: Draft

## Role

The relay is the totem's single read/write surface: it stores notes, serves
all connected users, and is the convergence point for every on-ramp
(`06-interaction.md`). Totem-to-totem sync is relay-to-relay.

## Requirements

A totem's relay MUST be a standard nostr relay (NIP-01 client protocol) and
MUST support **NIP-77** — negentropy set reconciliation — so totems can
exchange note sets efficiently during encounters. Beyond that, any generic
relay implementation qualifies: there is no Totem-specific relay protocol.
The relay MUST be reachable on the standardized relay port
(`07-conventions.md`).

The relay SHOULD be self-contained (embedded database, no external services)
because a totem is a standalone device.

## Sync

Per `03-network.md`, sync uses NIP-77 over the same websocket, followed by
REQ/EVENT transfers. The **flatness rule** applies: a totem connecting to
another totem's relay uses it exactly the way a human user's client does —
same ports, same protocol, no privileged peer-to-peer path. A totem is simply
a client whose npub is on the other's contact list.

## Permission and moderation layer

The relay MAY include a permission layer so the owner can moderate — e.g.
remove notes, restrict what guest users write. Open policy questions (guest
write rights, differing treatment of FIPS-authenticated peers vs anonymous
AP guests) are tracked in `09-open-questions.md`.

## Reference implementation

[strfry](../references/strfry) is the reference relay:

- self-contained — all data in LMDB on the local filesystem, no external
  database;
- NIP-77-capable (negentropy sync with clients and between relays);
- durable writes, hot-reloadable config;
- a **plugin interface** — the natural home for the permission/moderation
  layer, so policy lives beside the relay instead of forking it.

Other conforming relays are acceptable; strfry is what we prototype against.

## NIP-11 declaration

The relay serves its NIP-11 info document over HTTP at the standard relay
port. The totem marker and npub ride **standard NIP-11 fields**
(`07-conventions.md`): no Totem-specific relay customization is required —
any conforming relay whose operator can set `info.name` and `info.self` can
declare totemhood. This document is the recognition surface used by
`02-identity.md`; the challenge itself is served by the control plane on
the web port (`10-control-plane.md`), so the relay stays a stock, unproxied
server.
