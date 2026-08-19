# Totem — Design & Specification Phase

## Context

We are designing **Totem**, an open-source personal hardware device platform. A **totem** is a small, self-contained device that a user carries around. Each totem runs its own Nostr relay, where notes are posted. When two totems come within range of each other, they discover one another, pair, and sync the notes stored in their internal relays. By simply walking around, users grow an organic, sneakernet-style network. That is the core experience of Totem.

## First principles

1. **Fun.** Carrying a totem and bumping into other totems should feel playful and rewarding — the network exists because people move.
2. **Sneakernet topology.** Notes travel by physically carrying totems: users post notes to a totem's relay, and totems sync when they meet. No infrastructure required.
3. **Open and multi-user.** A totem is not a single-owner device: *any* user can connect to any totem and use it. Only device administration is owner-only.
4. **Open and hackable.** An open-source platform users can build from off-the-shelf hardware. The reference prototype is the Raspberry Pi Zero (W), but the design must stay hardware-agnostic so anyone can implement a totem on their own hardware.

## Architecture: three layers

1. **Network layer.** WiFi/Bluetooth, using [FIPS](../references/fips) as the multi-transport mesh framework. All transports are unified, so totems can connect over any of them. Totems must be able to discover other totems nearby, connect/pair, and sync notes.
2. **Nostr relay layer.** A standard nostr relay running on the totem, storing notes and serving all connected users. Any generic relay implementation qualifies — there is no Totem-specific relay specification — **except** it must support [NIP-77](../references/negentropy.md) (negentropy set reconciliation) so totems can exchange note sets efficiently. It may include a permission layer so the owner can moderate (e.g. remove notes). [strfry](../references/strfry/) is our reference relay: it is self-contained (LMDB, no external database), NIP-77-capable, syncs relay-to-relay, and exposes a plugin interface that can host the permission/moderation layer.
3. **Kernel layer.** The layer connecting software to hardware, abstracting low-level APIs so different devices and peripherals can be implemented. We intend to build this on the napplet model ([NAPs](../references/naps), [Kehto](../references/web) as reference implementations). Important constraint: the NAPs track presently only expresses the **web projection** of the protocol — it has no concept of a headless nostr applet (a "happlet"?). We intend to reuse the same wire format and protocol, since there are already interfaces we can leverage in Totem and a simple track for defining new interfaces.

A universal on-device **message bus** is desirable because various services require direct access to one another and to core runtime services, and the existing protocol and tooling lend themselves well to this. For this to work, a new projection must be defined: **IPC**.

Kernel parts identified so far: **shell, runtime, control plane, device manager, drivers**.

## Identity and inter-totem relations

- **One identity everywhere.** A totem has a single Nostr keypair: the same npub is its internal (device) identity *and* its FIPS network identity. FIPS already authenticates nodes with nostr keypairs, so when two totems meet over the mesh they each know the other's npub — authenticated, no extra protocol.
- **Totem recognition.** A totem declares itself in its relay's info document (NIP-11): a totem marker plus its npub. This reuses standard nostr discovery and makes the claim verifiable — the document is served at the standardized relay port of a peer whose npub is already authenticated (over FIPS), and the declared npub must match. The recognition flow: on each new authenticated FIPS peer, the totem probes the standard relay port with a NIP-11 request; a response with the totem marker means "this peer is a totem", anything else means it is not (and is simply ignored). The same probe works on the WiFi AP path. Probe verdicts are cached per npub so re-encounters are free.
- **Contacts.** Inter-totem relations use standard **NIP-02 kind 3** contact/follow lists: when totems meet, each follows the other by publishing a kind 3 event (signed by its npub) to its own relay. Mutual follows = "friends". This is deliberately plain nostr — flat, self-signed, stored in the relay like any other event.
- **Relations ride the sync pipeline.** Because contact lists are ordinary events, they propagate between totems through the same NIP-77 negentropy sync as notes. A third totem meeting either party learns the relation as a side effect of syncing — the social graph grows with the sneakernet, no extra machinery.
- **Room to grow.** Since relations are signed events, richer dynamics later (encounter records, lineage, badges, games) can be new event kinds over the same substrate, without protocol changes.

## Interaction model: on-ramps and the convergence point

Every path into a totem terminates at the same place: its services, on standardized ports, behind the same relay. The fabric underneath only determines *who can reach the totem* and *from how far* — not how it is used.

### On-ramps

- **WiFi AP (proximity on-ramp).** The totem emits a regular WiFi access point. Users join it with any phone or laptop — no FIPS, no special software, nothing to install — and immediately reach the standardized ports. This is the zero-friction path and must stay that way: no feature may ever require a guest to run FIPS.
- **FIPS (reach on-ramp).** FIPS is a general mesh fabric, not a totem-only one. Any user running FIPS on their laptop or phone becomes a full peer: authenticated npub, routable address, and access to the same standardized ports. Over the IP overlay this means reaching a totem that is not nearby at all (e.g. behind NAT, at home) — end-to-end encrypted, no port forwarding. Over Bluetooth it is a local, infrastructureless proximity mesh.
- **Totem-to-totem.** Totems are simply FIPS peers to each other (or, as a fallback, can join another totem's AP like any station).

### Conventions that make this work

- **Standardized ports** for the relay and the web app: once you can reach a totem by any means, you know where its services live.
- **Standardized address on the AP network**: the totem is always reachable at its AP's gateway address (and/or an fd00 ULA), and/or a captive portal landing on the web app. Guests never need to guess where the totem is.
- **Flatness is a design rule.** Totems connecting to each other use the relay exactly the same way human users do — same ports, same protocol, no privileged peer-to-peer path. A totem is simply a client whose npub is on the other's contact list. One access model, no footguns.
- **The relay is the convergence point.** The totem's sync engine pulls notes in via FIPS/negentropy and writes them to the relay database; every connected user reads that same database regardless of on-ramp. A guest on WiFi sees notes that arrived through the mesh without knowing or caring how they got there.

### Users and roles

- The **owner** uses the web app (served on the standard HTTP port) to see and control the state of the totem.
- **Other users** get the totem's **relay URL** and can connect to it with any nostr client and start posting immediately.
- Note the asymmetry: a FIPS-connected user arrives with a verified npub, while a WiFi guest is an anonymous IP. Relay policy may treat them differently later.

### Lore: the totem as ambassador

Because all on-ramps converge on the same relay, a user can post a note to their totem remotely through the FIPS overlay, and the totem then carries it physically: when it meets other totems, the note propagates through the sneakernet. The totem acts as its owner's ambassador in the physical network.

## Goal of this phase

Produce a specification we can build on and iterate against, defining — in a high-level, hardware-abstracted way:

- The stack that composes a totem, and each layer's abstraction and rationale.
- How the kernel works, including the IPC / message-bus layer and the new IPC projection.
- How totems connect to each other (net code): discovery, recognition, pairing, and note sync.
- The identity model: unified npub, totem recognition via NIP-11, and contact/friendship semantics.
- The interaction model: on-ramps (WiFi AP, FIPS), the convergence point, and user roles.
- The Totem protocol conventions: standardized ports and addresses, NIP-11 totem marker, sync behavior, relay requirements (NIP-77).

Alongside the spec, write a small set of **user stories** to support and validate it.

## Main demo (early milestone)

Build the kernel, relay, and network layer; flash them onto two Raspberry Pi Zeros; have two users walk past each other and watch their totems connect, recognize each other, befriend (kind 3), and sync notes.

## Open questions to resolve during design

- Terminology and shape of the headless applet (happlet?) and the IPC projection.
- Radio usage: on a single-radio device (Pi Zero W), the natural split is WiFi-as-AP for guests and Bluetooth for the FIPS proximity mesh, with the IP overlay when upstream internet exists — confirm this and define what multi-radio devices should do.
- Is a totem joining another totem's AP as a station a supported v1 behavior, or only a fallback? (It competes for airtime with guest service.)
- Guest experience: captive portal on join? Is the web app read-only for non-owners?
- Relay policy: what may guest users write? Should FIPS-authenticated peers and anonymous AP guests be treated differently?
- Sync semantics: direction, filters, payload limits over Bluetooth.
- Privacy of relations: are kind 3 contact lists public, or visible only to the parties? Do we want encounter records (where a totem has been, whom it met), and at what visibility?
- Key management: does the owner use the totem's npub or a separate admin npub? What happens to contacts and mesh identity on key rotation?
- Is any HTTP liveness/capability endpoint needed beyond NIP-11 and signed events?
- What "shell" means on a headless device; which kernel parts are mandatory vs. optional per hardware target.
- Scale limits on constrained hardware: event volume, storage budget, sync duration during a brief encounter.

## Working mode

We are in the design phase — no implementation yet. First, analyze this brief and review the reference repositories. Then share your thoughts, insights, and recommendations, flagging risks and unknowns. We will discuss and iterate on the design together until we green-light it; only then do we write the specification.

## References

- `references/fips` — FIPS (Free Internetworking Peering System): self-organizing encrypted mesh over Nostr identities, transport-agnostic (WiFi, Bluetooth, Ethernet, serial); usable as a local mesh or an overlay on the existing internet.
- `references/naps` — NAP registry and governance: capability contracts between napplets and runtimes, and the projections concept.
- `references/web` — Kehto: web runtime for NIP-5D napplets (shell, runtime, ACL, services, firewall packages).
- `references/negentropy.md` — NIP-77: negentropy-based set reconciliation for efficient event syncing, client-relay and relay-relay.
- `references/strfry` — strfry: self-contained nostr relay (LMDB), NIP-77 sync, plugin interface for policy; our reference relay implementation.
