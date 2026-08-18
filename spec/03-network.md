# 03 — Network Layer (Net Code)

Status: Draft

## Role

The network layer is what makes totems meet: it carries the traffic for
discovery, recognition, and sync, and it provides the guest on-ramp. The
behavioral software implementing this layer is called the **net code**.

## FIPS as the mesh framework

Totem-to-totem connectivity uses [FIPS](../references/fips), the Free
Internetworking Peering System: a self-organizing encrypted mesh built on
nostr identities, operating over arbitrary transports.

What FIPS provides, and what Totem relies on:

- **Transport unification.** Bluetooth, WiFi, Ethernet, serial, or an IP
  overlay — same protocol, same mesh. A totem can connect to another totem
  over any of these.
- **Authenticated identity.** Peers authenticate with nostr keypairs; see
  `02-identity.md`.
- **Routable addresses.** A peer that joins gets a routable address, so the
  standardized ports (`07-conventions.md`) are directly reachable.

Deployment modes relevant to Totem:

- **Ground-up proximity mesh** (Bluetooth, or WiFi without infrastructure):
  totems that come within range beacon, discover, and form peer links
  automatically.
- **IP overlay:** when a totem has upstream internet, FIPS lets peers reach
  it behind NAT without port forwarding — the "reach" on-ramp
  (`06-interaction.md`).

## Radio usage

On a single-radio device (the Pi Zero W reference profile), the natural split:

- **WiFi = service interface** — the AP for guests (`06-interaction.md`).
- **Bluetooth = totem-to-totem proximity transport** for FIPS.
- **FIPS IP overlay** when upstream internet exists.

Multi-radio devices SHOULD follow the same logical split (AP on one radio,
mesh transports on the others) but MAY interleave as capacity allows. See
`09-open-questions.md` for the coexistence question on constrained hardware.

## Discovery and pairing sequence

The end-to-end sequence when two totems meet (the normative trigger of the
recognition probe is defined in `02-identity.md`):

1. **Link.** Transports discover each other (FIPS beaconing / AP join).
   FIPS authenticates both sides; each learns the other's npub.
2. **Recognize.** Each totem probes the other's standard relay port with a
   NIP-11 request and checks the totem marker + npub match
   (`02-identity.md`).
3. **Befriend.** Each totem publishes a kind 3 contact event following the
   other (`02-identity.md`).
4. **Sync.** Both relays run NIP-77 negentropy reconciliation over the same
   connection and exchange the missing events (`04-relay.md`).
5. **Part.** When the peers leave range, transports drop the link; sync state
   is resumable on the next encounter.

## Sync lifecycle

- **Trigger:** a successful recognition verdict (step 2 above).
- **Mechanism:** NIP-77 (`references/negentropy.md`) — negentropy set
  reconciliation over the relay websocket, then event transfer via REQ/EVENT.
  Relay-to-relay or client-style; see `04-relay.md` for the flatness rule.
- **Content:** everything the relays' sync filters admit — notes and the
  social graph (kind 3) alike.
- **Resumability:** syncs SHOULD tolerate interruption (brief encounters);
  a next encounter resumes from the reconciled state.

Direction, filters, and payload limits — especially over Bluetooth — are open
questions (`09-open-questions.md`).

## AP-station fallback

A totem MAY join another totem's AP as a station and use the flat path
(standard ports, NIP-11 probe, relay sync) without FIPS. This works for free
with the conventions but competes for airtime with guest service; whether it
is a supported v1 behavior or only a fallback is an open question
(`09-open-questions.md`).
