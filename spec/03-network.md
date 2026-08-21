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

The Pi Zero W reference profile has one onboard combo chip, but it must not be
modeled as one exclusive software mode. Linux exposes distinct Wi-Fi and
Bluetooth controllers, and the Wi-Fi PHY itself advertises valid concurrent
interface combinations. The net code MUST inspect those capabilities and live
interfaces instead of assuming that enabling BLE, station Wi-Fi, AP, or P2P
necessarily disables every other role.

The device manager is the policy-free hardware boundary. It exposes:

- physical Wi-Fi/Bluetooth inventory, driver/firmware/controller metadata,
  channels, roles, interface modes, and supported/unsupported operations;
- kernel-declared Wi-Fi concurrency combinations and the live mode, channel,
  connection, and addresses of every interface;
- Wi-Fi and Bluetooth radio/block state and explicit setters;
- station scan/connect/disconnect and AP create/stop;
- Wi-Fi Direct discovery, peer inventory, and create-or-join/list/remove group
  lifecycle;
- Wi-Fi Aware/NAN capability detection, bounded publish/subscribe discovery,
  match inventory, and typed NAN data-path support or an explicit unsupported
  reason;
- bounded, independently identified BLE discovery sessions, structured
  advertisements, advertising lifecycle, generic connection state, and GATT
  client inventory/read/write/notification lifecycle;
- bounded LE L2CAP CoC listeners and connections, assigned-PSM advertising,
  and descriptor handoff that leaves payload framing, identity, cryptography,
  routing, and peer policy with FIPS;
- typed hardware events plus explicit operation timeouts and idempotent
  teardown.

It MUST NOT decide which role to prefer, when to switch, which peer to trust,
whether to sync, or what packets to send. A higher-level controller uses the
capability and status APIs, applies operator/product policy, and binds traffic
to the interface/address returned for the selected link.

An LE CoC listener MUST fail closed when its PSM advertisement cannot be
registered: an undiscoverable open listener is not a successful primitive.
The advertisement carries only the FIPS service UUID and the assigned 16-bit
PSM, never an npub or trust decision. A NAN discovery function likewise
carries caller-supplied opaque service information; the device manager does
not interpret it as peer identity. NAN data-path results MUST return a scoped
IPv6 address and interface suitable for interface-bound FIPS UDP, or report
`supported: false` without changing infrastructure Wi-Fi, FIPS, or routes.
Support reporting MUST include the current process authority required by the
platform control surface; the implementation MUST NOT grant broad network
administration capability to the device-manager service merely to turn a
hardware mode into `supported: true`.

### Measured Pi Zero W concurrency

Both armv6 and armv7 bench units report the `brcmfmac` PHY modes `managed`,
`AP`, `P2P-client`, `P2P-GO`, and `P2P-device`. Their kernel exposes these
valid combinations:

1. up to two managed interfaces, one P2P-device, and one P2P-client-or-GO;
   three interfaces total across at most two channels;
2. one managed, one AP, one P2P-client, and one P2P-device; four interfaces
   total on one channel.

Live validation formed a reciprocal NetworkManager Wi-Fi Direct group between
`totem` and `metot` on channel 7 while both retained their channel-7 managed
infrastructure connection and FIPS TUN. The group negotiated totem as GO and
metot as client, assigned link-local IPv4/IPv6 addresses, carried
interface-bound ICMP with zero loss, and completed a bidirectional UDP
request/ack exchange. Both sides had to activate the documented
`wifi-p2p` create-or-join connection for the PBC negotiation; one-sided
activation timed out without dropping infrastructure Wi-Fi.

BLE discovery and structured advertisement reception were also validated
while managed Wi-Fi and FIPS remained active. These measurements prove useful
coexistence on the current bench stack; they do not guarantee arbitrary
channel/role combinations on other adapters. The live capability matrix is
authoritative, and unsupported/conflicting requests MUST fail explicitly.

The AP conventions (`07-conventions.md`) apply only when an AP is actually
active. Infrastructure station, AP, P2P, and BLE are mechanisms that may
coexist when the reported hardware constraints allow; role selection remains
a policy question (`09-open-questions.md`).

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

A totem MAY join another totem's AP as a station and use the flat path
(standard ports, NIP-11 probe, relay sync) without FIPS. This works for free
with the conventions but competes for airtime with guest service; whether it
is a supported v1 behavior or only a fallback is an open question
(`09-open-questions.md`).
