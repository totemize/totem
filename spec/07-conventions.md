# 07 — Protocol Conventions

Status: Draft

This is the normative registry of Totem's protocol conventions: everything a
totem implementer MUST honor for interop. Values marked **TBD** are decided
during this design phase; this document is their single home
(see `README.md` rules).

## Port registry

Once a client can reach a totem by any means, it knows where the services
live.

| Service | Port | Notes |
|---------|------|-------|
| Relay (websocket + NIP-11 HTTP) | **TBD** | Standard nostr relay port |
| Web app (owner control / guest info) | **TBD** | HTTP |

A totem MUST serve both on the ports registered here, on every on-ramp.

## AP network conventions

- The totem MUST be reachable at its AP's **gateway address** (and/or an
  fd00 ULA — **TBD**) so guests never guess where the totem is.
- A captive portal landing on the web app is **TBD** (open question).

## NIP-11 totem marker

The relay's NIP-11 info document (served over HTTP at the standard relay
port) MUST include:

- a **totem marker** field identifying the relay's host as a totem
  (field name **TBD**);
- the totem's **npub**, which MUST match the npub FIPS authenticates for the
  node (`02-identity.md`).

Clients use this document for recognition; a missing marker means "not a
totem".

## Relay requirements

- The relay MUST implement NIP-01 and NIP-77 (see `04-relay.md`).
- Sync behavior: NIP-77 negentropy reconciliation over the relay websocket,
  then REQ/EVENT transfers — identical for users and totems (flatness rule,
  `06-interaction.md`).

## Sync conventions

- Sync filters, direction, and payload limits: **TBD** (`09-open-questions.md`).
- Syncs SHOULD tolerate interruption and resume on the next encounter
  (`03-network.md`).

## Contacts convention

Inter-totem relations are NIP-02 kind 3 events published to the totem's own
relay; mutual follows = friends (`02-identity.md`). No extra protocol.
