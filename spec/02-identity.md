# 02 — Identity and Inter-Totem Relations

Status: Draft

## One identity everywhere

A totem has a single Nostr keypair. The same npub is:

- its **internal (device) identity** — the actor that signs events, owns the
  contact list, and is granted administrative meaning, and
- its **FIPS network identity** — the keypair FIPS uses to authenticate the
  node on the mesh.

FIPS nodes authenticate each other with nostr keypairs, so when two totems
meet over the mesh they each already know the other's npub — authenticated,
no extra protocol.

Consequences that MUST hold:

- Every claim a totem makes about itself can be a signed nostr event — self-
  authentic and verifiable by any third party.
- The npub identifies the totem *as an actor*, not the relay's contents: the
  relay serves events from many pubkeys. The spec's vocabulary keeps these
  separate.

Key management (owner key vs. device key, rotation) is an open question — see
`09-open-questions.md`. Until resolved, the assumption above stands: one
device keypair, one identity.

## Totem recognition

Problem: over any fabric, a totem must distinguish *another totem* from a
regular user peer.

### Declaration

A totem declares itself in its relay's NIP-11 info document: a **totem
marker** plus the totem's **npub** (see `07-conventions.md` for the field).
The declaration rides an existing, standardized nostr discovery mechanism —
no new endpoint.

### Recognition flow

1. FIPS authenticates a new peer; the totem's net code learns
   *(peer npub, routable address)*.
2. On each new authenticated peer, the net code probes the standardized relay
   port with a NIP-11 request (`GET /` with `Accept: application/nostr+json`).
3. Verdict:
   - Connection refused / nothing listening → the peer is not a totem.
     Ignore it.
   - A valid NIP-11 document containing the totem marker → the peer is a
     totem. The declared npub MUST match the npub FIPS authenticated; a
     mismatch is a red flag and MUST be treated as "not a totem".
4. On a positive verdict, the totem proceeds with totem behavior: open the
   relay websocket, run sync (`03-network.md`), and update its kind 3 contact
   list with the peer's npub.

The same probe works on the WiFi AP path: any client reaching the standard
relay port can read the NIP-11 document, and a totem joining another totem's
AP as a station recognizes it identically.

Probe verdicts SHOULD be cached per npub so re-encounters skip the probe.

### Why not alternatives

- A dedicated HTTP "hello" endpoint works but any phone could claim
  totemhood; it needs authentication, and signed nostr events already are
  that. NIP-11 + npub match gives the same result with no new surface.
  Whether a liveness/capability endpoint is needed beyond NIP-11 remains an
  open question (`09-open-questions.md`).
- Piggybacking the marker on FIPS node metadata would couple totem logic to
  FIPS internals and duplicate what NIP-11 already standardizes.

## Contacts

Inter-totem relations use standard **NIP-02 kind 3** contact/follow lists:

- When totems meet and recognize each other, each follows the other by
  publishing a kind 3 event (signed by its npub) to its own relay.
- **Mutual follows = friends.**
- This is deliberately plain nostr — flat, self-signed, stored in the relay
  like any other event. No contact-database format is invented; storage is
  the relay DB the totem already has.

## Relations ride the sync pipeline

Because contact lists are ordinary events, they propagate between totems
through the same NIP-77 negentropy sync as notes. A third totem meeting
either of two friends learns the relation as a side effect of syncing — the
social graph grows with the sneakernet, no extra machinery.

## Room to grow

Since relations are signed events, richer dynamics later — encounter records,
lineage, badges, games — can be new event kinds over the same substrate,
without protocol changes. These are future directions, not commitments
(`09-open-questions.md` covers visibility and privacy decisions they imply).
