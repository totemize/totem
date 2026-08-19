# 05 — Kernel

Status: Draft

## Role

The kernel is the layer connecting the software to the hardware: it abstracts
low-level APIs so different devices and peripherals can be implemented.
Everything above it (relay, web app, net code) is hardware-agnostic and talks
to hardware only through the kernel.

## Foundations: napplets and NAPs

We intend to build the kernel on the napplet model:

- [NAPs](../references/naps) define the **capability seam** between a
  napplet and its runtime — the contract for what a runtime offers (relay
  access, storage, intents, …) and how a napplet asks for it. The contract is
  fixed; delivery varies by **projection**.
- [Kehto](../references/web) is the reference runtime implementation for the
  web projection (shell, runtime, ACL, services, firewall packages).

**Constraint:** the NAPs track presently only expresses the **web projection**
of the protocol. It has no concept of a headless nostr applet. We intend to
reuse the same wire format and protocol because there are already interfaces
we can leverage in Totem, and a simple track for defining new interfaces.

## Happlets

A **happlet** (provisional name; "headless applet" — happ? hApplet?) is a
nostr applet running without a browser: a small, single-purpose program the
totem runtime composes and provides capabilities to. Happlets use NAP
contracts; what changes is the projection.

## IPC projection

A universal on-device **message bus** is desirable because various services
require direct access to one another and to core runtime services, and the
existing protocol and tooling lend themselves well to this.

For this to work, a new projection must be defined: **IPC** — the binding of
the NAP seam onto the local message bus, with the same wire format as the web
projection.

What the IPC projection MUST define:

- how a happlet connects to the bus and identifies itself (its npub/manifest);
- how capability negotiation works outside the browser sandbox model;
- how existing NAPs (relay, storage, …) map onto bus messages;
- the track for proposing new IPC-native interfaces.

## Kernel parts

The parts identified so far:

| Part | Role |
|------|------|
| **Shell** | What "shell" means on a headless device is an open question (`09-open-questions.md`); tentatively the composition/entry layer. |
| **Runtime** | Hosts happlets: dispatch, sessions, capability enforcement (mirroring Kehto's runtime). |
| **Control plane** | Management surface: state, configuration, the backend for the owner's web app (`06-interaction.md`). |
| **Device manager** | enumerates and manages hardware peripherals. |
| **Drivers** | hardware-specific implementations behind the kernel's abstractions. |

Which parts are mandatory vs. optional per hardware target is an open
question (`09-open-questions.md`).

## v1 scope vs. deferred

The **v1 kernel is the demo-minimal kernel**: process supervision, the device
adapters the reference profile needs, and the control-plane backend for the
web app. Nothing more is required for the demo milestone (`08-stories.md`).

The **happlet model and the IPC projection are future directions**: kept in
this document as design intent, specified when a use case demands them. The
v1 kernel MUST NOT block on them.
