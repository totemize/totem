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
  authentic and verifiable by any third party. Signed ≠ stored: publication
  in a relay is optional, not part of the signature.
- The npub identifies the totem *as an actor*, not the relay's contents: the
  relay serves events from many pubkeys. The spec's vocabulary keeps these
  separate.

Key management (owner key vs. device key, rotation) is an open question — see
`09-open-questions.md`. Until resolved, the assumption above stands: one
device keypair, one identity.

## Totem recognition

Problem: over any fabric, a totem must distinguish *another totem* from a
regular user peer.

### Declaration (the hint)

A totem advertises itself in its relay's NIP-11 info document using
**standard NIP-11 fields only** (`07-conventions.md`): the relay `name`
carries the totem marker (a `!Totem` prefix), and `self` carries the device
npub. This is an unsigned **hint**: a cheap pre-filter so peers only run the
authentication challenge at things that look like totems. It authenticates
nothing by itself — and because both fields are standard, any conforming
relay whose operator can set them can declare totemhood: no relay fork, no
proxy in front of the relay, no custom schema.

### Challenge (the proof)

The NIP-11 marker is only a hint; recognition is proven by a challenge —
the NIP-98/NIP-42 pattern (verifier issues a nonce, prover returns a fresh
signed event bound to it) played over plain HTTP on the same server that
serves NIP-11:

```
Totem A (prober)                         Totem B (peer)
      │                                        │
 1.   │ GET /  (Accept: nostr+json)            │  ← relay port
      │───────────────────────────────────────▶│
 2.   │ 200 NIP-11 doc with totem marker       │  ← unsigned hint
      │◀───────────────────────────────────────│
 3.   │ A mints a nonce (16 random bytes hex)  │
      │ GET /totem/challenge?nonce=9a3f..c1    │  ← web port (totemd)
      │───────────────────────────────────────▶│
 4.   │ B's control plane signs an event over │
      │ the nonce: 200 { "event": {...} }      │
      │◀───────────────────────────────────────│
 5.   │ A verifies, then discards nonce+event  │
```

The signed event is never published or stored anywhere:

```json
{
  "kind": 27235,
  "pubkey": "<B's hex pubkey>",
  "created_at": 1731974400,
  "tags": [
    ["nonce", "9a3f...c1"],
    ["u", "http://[B-addr]:PORT/totem/challenge"],
    ["method", "GET"]
  ],
  "content": "",
  "sig": "<signature>"
}
```

The prober's verification checklist:

1. the signature is valid for `pubkey` (proof of key control);
2. `pubkey` matches the expected npub — over FIPS the transport-authenticated
   peer npub, over AP the npub claimed in the NIP-11 document;
3. the `nonce` tag equals the nonce sent (binds response to this exchange);
4. `created_at` is fresh (window **TBD**, `07-conventions.md`).

Pass → totem. Anything else → not a totem; ignore.

Properties: the challenge is one-way (mutual recognition is the symmetric
exchange, both directions in parallel during pairing); stateless on both
sides; replay-proof by construction (single-use nonce + freshness window);
and it rides the totem's web server (`10-control-plane.md`) — no listener
beyond the web port a totem serves anyway, and no involvement of the relay
server at all.

Values are pinned in `07-conventions.md`: the endpoint is `/totem/challenge`
on the web-app port, and the event kind is 27235 (NIP-98's) with an added
`nonce` tag. The freshness window is still TBD there.

### Recognition flow

1. FIPS authenticates a new peer; the net code learns
   *(peer npub, routable address)*.
2. The net code probes the standardized relay port with a NIP-11 request.
   No marker → the peer is not a totem; ignore it.
3. **Challenge.** The probing totem runs the challenge protocol above with
   the peer. The response is verified and discarded — it is never stored in
   any relay.
4. **Verdict.** Over FIPS, the signing npub MUST match the
   transport-authenticated npub — recognition is fully bound to the mesh
   identity, and no separate endpoint-binding proof is needed. Over the AP
   path, the signature proves control of the claimed key — which is all
   "I am totem npub X" can mean without a transport-authenticated key, and
   impersonating a *specific* totem remains impossible without its key.
   (Checklist step 2 above.)
5. On a positive verdict, the totem proceeds with totem behavior: open the
   relay websocket, run sync (`03-network.md`), and update its kind 3 contact
   list with the peer's npub.

The same probe + challenge works on the WiFi AP path: a totem joining another
totem's AP as a station recognizes it identically.

Recognition verdicts are per-encounter; nothing is cached across encounters.

### Why not alternatives

- **A persistent declaration event** stored in the relay is verifiable but
  wastes a permanent record just for authentication. The ephemeral challenge
  gives the same proof with nothing stored (signed ≠ stored).
- **A bare HTTP "hello" endpoint** — any phone could claim totemhood; it
  needs authentication, and the challenge response already is that, reusing
  standard nostr signing.
- **Piggybacking the marker on FIPS node metadata** — couples totem logic to
  FIPS internals and duplicates what NIP-11 + the challenge already do.
- **Formally specifying FIPS endpoint binding** — unnecessary: the npub match
  in step 4 does the binding.

## Contacts

Inter-totem relations use standard **NIP-02 kind 3** contact/follow lists:

- When totems meet and recognize each other, each follows the other by
  publishing a kind 3 event (signed by its npub) to its own relay.
- **Mutual follows = friends.**
- This is deliberately plain nostr — flat, self-signed, stored in the relay
  like any other event. No contact-database format is invented; storage is
  the relay DB the totem already has.
- All kind 3 updates are issued by the **net code — the totem's single
  writer** — so follow-list updates are serialized read-modify-sign-write by
  construction.

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
