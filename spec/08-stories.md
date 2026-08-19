# 08 — User Stories and Demo Milestone

Status: Draft

Each story traces to the spec documents it validates. A story that cannot
point at its sections is a sign the design has a hole.

## Stories

### S1 — The guest passing by

*Ada is at a café. She sees a totem on the table and joins its WiFi with her
phone. A page opens showing the totem's relay URL. She pastes it into her
nostr client, reads the notes on it, and posts one of her own.*

Validates: `06-interaction.md` (AP on-ramp, zero-friction rule, guest role),
`07-conventions.md` (AP gateway address, relay port), `04-relay.md`
(standard relay, guest writes).

### S2 — The owner at home

*The owner connects to their totem's web app and checks its state: battery,
storage, how many totems it met today, its contact list. They remove an
offensive note from the relay.*

Validates: `06-interaction.md` (owner role), `04-relay.md` (permission/
moderation layer), `05-kernel.md` (control plane behind the web app).

### S3 — Two totems meet

*Two people carrying totems walk past each other. The totems discover each
other over Bluetooth via FIPS, authenticate, recognize each other via the
NIP-11 marker, befriend (mutual kind 3), and sync their relays via
negentropy. Both walk away carrying each other's notes.*

Validates: `03-network.md` (discovery/pairing sequence, sync lifecycle),
`02-identity.md` (recognition flow, contacts), `04-relay.md` (NIP-77),
`07-conventions.md` (relay port, marker).

### S4 — The social graph grows

*Later, one of those totems meets a third totem. During sync, the third
totem learns the two are friends — the kind 3 events arrived with the notes.*

Validates: `02-identity.md` (relations ride the sync pipeline).

### S5 — The ambassador

*While her totem sits at home behind NAT, Bea posts a note to it through the
FIPS overlay from her laptop. The next day the totem travels in her bag and
meets other totems; Bea's note propagates through the sneakernet.*

Validates: `06-interaction.md` (FIPS reach on-ramp, convergence point,
ambassador property), `03-network.md` (IP overlay mode).

### S6 — Build your own

*A maker builds a totem from off-the-shelf parts different from the Pi Zero
W, following the spec: same conventions, same behavior. It interops with
every totem it meets.*

Validates: `01-overview.md` (hardware-agnostic stance), `05-kernel.md`
(abstraction), `07-conventions.md` (the compliance checklist).

## Demo milestone (first acceptance test)

Build the kernel, relay, and network layer; flash them onto two Raspberry Pi Zeros; have two users walk past each other and watch their totems connect,
recognize each other, befriend (kind 3), and sync notes.

This is S3 made real — the minimum end-to-end proof of the platform. It
exercises every layer: kernel (processes on the device), relay (storage and
NIP-77), net code (FIPS over Bluetooth, discovery, recognition), and the
conventions that tie them together.
