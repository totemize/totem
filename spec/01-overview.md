# 01 — Overview

Status: Draft

## What Totem is

Totem is an open-source personal hardware device platform. A **totem** is a
small, self-contained device that a user carries around. Each totem runs its
own Nostr relay, where notes are posted. When two totems come within range of
each other, they discover one another, recognize each other, and sync the
notes stored in their internal relays. By simply walking around, users grow an
organic, sneakernet-style network.

## Lore

A totem is a fun device that creates an organic, sneakernet-style internet:
users carry their totems, post notes into them, and the totems exchange notes
when they meet. Because every on-ramp converges on the same relay
(see `06-interaction.md`), a user can post to their totem remotely and the
totem then carries the note physically into the sneakernet. The totem acts as
its owner's ambassador in the physical network. The network exists because
people move.

## First principles

1. **Fun.** Carrying a totem and bumping into other totems should feel playful
   and rewarding — the network exists because people move.
2. **Sneakernet topology.** Notes travel by physically carrying totems: users
   post notes to a totem's relay, and totems sync when they meet. No
   infrastructure required.
3. **Open and multi-user.** A totem is not a single-owner device: *any* user
   can connect to any totem and use it. Only device administration is
   owner-only.
4. **Open and hackable.** Users can build a totem from off-the-shelf
   hardware. The reference prototype is the Raspberry Pi Zero (W), but the
   design is hardware-agnostic: anyone can implement a totem on their own
   hardware.

## System overview

A totem is composed of three layers:

1. **Network layer** — WiFi/Bluetooth using FIPS as the multi-transport mesh
   framework, so all transports are unified and totems can connect over any
   of them. Defined in `03-network.md`.
2. **Nostr relay layer** — a standard nostr relay storing notes and serving
   all connected users. Defined in `04-relay.md`.
3. **Kernel layer** — connects software to hardware, abstracting low-level
   APIs so different devices and peripherals can be implemented. Defined in
   `05-kernel.md`.

Cross-cutting: the **identity model** (`02-identity.md`) and the **interaction
model** (`06-interaction.md`) bind the layers together; the **protocol
conventions** (`07-conventions.md`) are the normative surface an implementer
must honor.

```
            users (browser / nostr client)        other totems
                 │            │                        │
        WiFi AP (proximity)  FIPS (reach)         FIPS mesh / AP
                 └────────────┴────────────┬───────────┘
                                          │
                            ┌─────────────┴─────────────┐
                            │  standardized ports (07)  │
                            ├───────────────────────────┤
                            │  web app    │   relay     │
                            └──────┬──────┴──────┬──────┘
                                   │  message bus │
                            ┌──────┴─────────────┴──────┐
                            │          kernel           │
                            └─────────────┬─────────────┘
                                          │
                                    hardware
```

The reference hardware (Pi Zero W) is a *profile*, not a requirement. A totem
MUST implement the software stack; how the hardware provides radios, storage,
and peripherals is abstracted by the kernel.

## Terminology

| Term | Meaning |
|------|---------|
| **Totem** | A device implementing this specification. |
| **Relay** | The nostr relay running on a totem. Any conforming generic implementation; see `04-relay.md`. |
| **Fabric** | A connectivity substrate: the WiFi AP, or the FIPS mesh. |
| **On-ramp** | A way for a client to reach a totem: the AP (proximity) or FIPS (reach). See `06-interaction.md`. |
| **Convergence point** | The relay database, where all on-ramps meet; the single read/write surface. |
| **Recognition** | Determining that a peer is a totem. See `02-identity.md`. |
| **Contacts / friends** | Inter-totem relations expressed as kind 3 follow lists. See `02-identity.md`. |
| **Sync** | NIP-77 negentropy set reconciliation between relays. |
| **Owner** | The human administrator of a totem. |
| **Guest** | Any non-owner user connecting to a totem. |
| **Net code** | The totem software implementing the network layer behavior. |
| **Pairing** | The full encounter sequence between totems: link → authenticate → recognize → befriend (`03-network.md`). |
| **Kernel** | The layer abstracting hardware access. See `05-kernel.md`. |
| **Happlet** | (Provisional name) a headless nostr applet. See `05-kernel.md`. |
