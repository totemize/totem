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
  at its AP's gateway address (and/or an fd00 ULA), and/or a captive portal
  landing on the web app. Guests never need to guess where the totem is
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
authentication** — an ephemeral signed event in the `Authorization` header,
the same mechanism totem recognition uses (`02-identity.md`). Unauthenticated
requests receive read-only access (state and the relay URL, nothing else),
so guests can never invoke control-plane operations. Initial provisioning
and key recovery remain open questions (`09-open-questions.md`).

## Guest experience

Open questions: captive portal on join? Is the web app read-only for
non-owners? (`09-open-questions.md`.)

## The ambassador property

Because all on-ramps converge on the same relay, a user can post a note to
their totem remotely through the FIPS overlay, and the totem then carries it
physically: when it meets other totems, the note propagates through the
sneakernet. The totem acts as its owner's ambassador in the physical network.
