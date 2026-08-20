# 06 — Interaction Model

Status: Draft

## Principle

Every path into a totem terminates at the same place: its services, on
standardized ports, behind the same relay. The fabric underneath only
determines *who can reach the totem* and *from how far* — not how it is used.

## On-ramps

### WiFi AP — the proximity on-ramp

The totem emits a regular WiFi access point. Users join it with any phone or
laptop — no FIPS, no special software, nothing to install — and immediately
reach the standardized ports. This is the zero-friction path and MUST stay
that way: no feature may ever require a guest to run FIPS.

### FIPS — the reach on-ramp

FIPS is a general mesh fabric, not a totem-only one. Any user running FIPS on
their laptop or phone becomes a full peer: authenticated npub, routable
address, and access to the same standardized ports. Over the IP overlay this
means reaching a totem that is not nearby at all (e.g. behind NAT, at home) —
end-to-end encrypted, no port forwarding. Over Bluetooth it is a local,
infrastructureless proximity mesh.

### Totem-to-totem

Totems are simply FIPS peers to each other — or, as a fallback, can join
another totem's AP like any station (`03-network.md`).

## Conventions that make this work

- **Standardized ports** for the relay and the web app: once you can reach a
  totem by any means, you know where its services live
  (`07-conventions.md`).
- **Standardized address on the AP network:** the totem is always reachable
  at `10.21.0.1`, including the web app on port `8080` and relay on port
  `7777`. Guests never need to guess where the totem is
  (`07-conventions.md`).
- **Flatness is a design rule.** Totems connecting to each other use the
  relay exactly the same way human users do — same ports, same protocol, no
  privileged peer-to-peer path. One access model, no footguns.

## The convergence point

The relay is the convergence point. The totem's sync engine pulls notes in
via FIPS/negentropy and writes them to the relay database; every connected
user reads that same database regardless of on-ramp. A guest on WiFi sees
notes that arrived through the mesh without knowing or caring how they got
there. Read path and write path are always "the local relay"; the fabric only
determines *which notes are in the DB* and *who can reach it*.

## Users and roles

| Role | What they do | How |
|------|--------------|-----|
| **Owner** | Sees and controls the state of the totem | The web app on the standard HTTP port, authenticated with NIP-98 |
| **Guest** | Reads notes, posts notes | Any nostr client pointed at the relay URL; the web app surfaces that URL |
| **FIPS peer** | Same as guest, but authenticated | Reaches the standard ports over the mesh |

Asymmetry to note: a FIPS-connected user arrives with a verified npub, while
a WiFi guest is an anonymous IP. Relay policy may treat them differently
later (`09-open-questions.md`).

### Owner authentication

Control-plane operations in the web app MUST require **NIP-98 HTTP
authentication** — an ephemeral signed event in the `Authorization` header.
Totem's profile adds a one-use server nonce and mandatory body hash, so replay
protection does not depend on RTC/NTP. Unauthenticated requests retain
read-only status, profile, policy, and relay access; they cannot mutate state.

A fresh v1 device is claimed by the first valid signer. The signer npub is
persisted locally as the single owner and all later mutations require that
same key. This intentionally assumes a trusted bootstrap network; physical
possession proof and lost-key recovery are deferred (`09-open-questions.md`).

The web app, challenge endpoint, and APIs are served by **totemd**
(`10-control-plane.md`). The relay remains a separate stock server on its own
port: owner control never flows through it, and the device secret never enters
the browser.

## Guest experience

The landing page's status, profile, and relay URL remain server-rendered and
usable without JavaScript. A small same-origin client enables claim and owner
forms through a NIP-07 browser signer. During early development it also offers
an explicit nsec escape hatch that signs only in page memory, never transmits
or persists the secret, and clears its key bytes on logout/navigation. Guests
still receive only the public read surface. Whether AP join opens it as a
captive portal remains an open question (`09-open-questions.md`).

## The ambassador property

Because all on-ramps converge on the same relay, a user can post a note to
their totem remotely through the FIPS overlay, and the totem then carries it
physically: when it meets other totems, the note propagates through the
sneakernet. The totem acts as its owner's ambassador in the physical network.
