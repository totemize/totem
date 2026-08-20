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

## Radio usage and modes

On a single-radio device (the Pi Zero W reference profile), the natural split:

- **WiFi = service interface** — the AP for guests (`06-interaction.md`).
- **Bluetooth = totem-to-totem proximity transport** for FIPS.
- **FIPS IP overlay** when upstream internet exists.

Multi-radio devices SHOULD follow the same logical split (AP on one radio,
mesh transports on the others) but MAY interleave as capacity allows. See
`09-open-questions.md` for the coexistence question on constrained hardware.

### Radio modes (single radio)

One radio means the totem is always in exactly one of these modes. The modes
are additive meeting paths — none precludes the others over the device's
lifetime, and the AP conventions (`07-conventions.md`) apply **only** to
AP-host mode:

| Mode | Radio role | Totem-to-totem path | Guest on-ramp |
|------|-----------|--------------------|---------------|
| Infra-station | joined to infrastructure WiFi | FIPS over shared L2 (mDNS discovery) | none (guests are on the infrastructure network) |
| AP-host | emitting the `!Totem` AP | other totems join as stations; FIPS over the AP L2 | yes (`06-interaction.md`) |
| BLE (v1.5) | WiFi per either mode above | FIPS BLE transport, no WiFi needed | per WiFi mode |

Notes:

- Totem-to-totem connectivity works in **every** mode — a shared-router
  deployment (two infra-stations) is the ordinary case and has no
  limitations versus any other mode.
- A totem in AP-host mode serves guests **and** acts as the meeting beacon
  for other totems: one emission, two product stories.
- V1 prefers any configured infrastructure connection. When none is active,
  the totem waits for NetworkManager's reconnect attempt, joins an existing
  `!Totem` if one is visible, or starts its own `!Totem` AP after a short
  randomized delay and final rescan. The delay makes one host likely when
  several disconnected totems arrive together.
- AP-host mode is sticky until reboot or an explicit infrastructure reconnect;
  v1 does not periodically drop connected guests merely to scan for an
  upstream network.

## Discovery and pairing sequence

The end-to-end sequence when two totems meet (the normative trigger of the
recognition probe is defined in `02-identity.md`):

1. **Link.** Transports discover each other (FIPS beaconing / AP join).
   FIPS authenticates both sides; each learns the other's npub.
2. **Recognize.** Each totem probes the other's standard relay port with a
   NIP-11 request and checks the totem marker, then runs the challenge to
   authenticate the claim (`02-identity.md`).
3. **Apply policy.** After recognition, each operator's totem independently
   decides whether to sync and whether to publish a kind 3 contact event
   (`10-control-plane.md`). With `policy.sync = true`, every recognized totem
   syncs; `false` restricts sync to existing friends.
4. **Sync (if permitted).** Both relays run NIP-77 negentropy reconciliation
   immediately and then periodically while the recognized encounter remains
   connected, exchanging newly missing events without requiring a reconnect
   (`04-relay.md`).
5. **Befriend (if `auto`, or after owner approval).** The totem publishes a
   kind 3 event following the other (`02-identity.md`).
6. **Part.** When the peers leave range, transports drop the link; sync state
   is resumable on the next encounter.

## Sync lifecycle

- **Trigger:** a successful recognition verdict (step 2 above). With
  `policy.sync = true`, friendship is not a prerequisite; `false` permits
  only peers already present in the friendship state.
- **Mechanism:** NIP-77 (`references/negentropy.md`) — one reconciliation
  immediately after recognition, then bounded periodic reconciliations for the
  life of that encounter. Each round uses the relay websocket and transfers
  events via REQ/EVENT. Relay-to-relay or client-style; see `04-relay.md` for
  the flatness rule.
- **Content:** everything the relays' sync filters admit — notes and the
  social graph (kind 3) alike.
- **Resumability:** syncs SHOULD tolerate interruption (brief encounters);
  a next encounter resumes from the reconciled state.

Sync is plain NIP-77 (`references/negentropy.md`) — negentropy defines its
own semantics; Totem adds no sync profile on top.

## AP-station fallback

Joining an existing `!Totem` before hosting a new AP is supported v1 fallback
behavior. FIPS LAN rendezvous authenticates peers over that shared L2, after
which recognition and relay sync use the ordinary FIPS path. A totem MAY also
use the flat AP path directly (standard ports, NIP-11 probe, relay sync), but
the implemented control-plane encounter trigger remains an authenticated FIPS
peer.
