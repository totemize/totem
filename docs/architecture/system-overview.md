---
title: System architecture
description: Runtime components, network surfaces, trust boundaries, and implementation status
---

<!-- generated-by: gsd-doc-writer -->

# System architecture

Totem combines four long-running services on a Raspberry Pi-class Linux
device. FIPS supplies the encrypted mesh and IPv6 overlay, strfry supplies the
local Nostr relay, `totemd` owns control-plane state, and the Python service
owns physical-device access. systemd supervises each process; Ansible installs
and verifies the stack.

This page separates the implementation in this repository from the broader
design in `spec/`. Where they differ, the implementation status below is the
operational truth and the spec remains the intended direction.

## Runtime map

```text
                           remote Nostr clients / peer relays
                                      │
                         ws://[device-address]:7777
                                      │
┌──────────────────────── Totem Linux device ─────────────────────────┐
│                                                                    │
│  wlan0 ◄── NetworkManager station/!Totem AP fallback               │
│    │                                                               │
│  physical links ──► FIPS ──► fips0 (fd00::/8 IPv6 overlay)         │
│                    │  │                                            │
│                    │  └─ [::1]:5354 DNS for <npub>.fips            │
│                    └──── /run/fips/control.sock                     │
│                                      │                              │
│                                      ▼                              │
│                         totemd FIPS watcher                         │
│                         │                  │                        │
│              public HTTP :8080      loopback bus :8081             │
│                                         │ POST /bus                 │
│                                         └ GET /bus/events (SSE)     │
│                                                                    │
│  strfry :7777 ──► LMDB /var/lib/strfry                            │
│                                                                    │
│  Python hardware API :8000 ──► managers ──► selected drivers       │
│                                         ├ display (SPI/GPIO)        │
│                                         ├ NFC                       │
│                                         ├ storage                   │
│                                         └ NetworkManager / Wi-Fi    │
└────────────────────────────────────────────────────────────────────┘
```

The relay is not proxied through `totemd`. Clients reach strfry directly over
the same standard WebSocket/Nostr protocol regardless of whether the IP path
is LAN, access point, or FIPS.

## Service inventory

| Unit | Process identity | Purpose | Durable state |
|---|---|---|---|
| `totem-wifi-fallback.service` | root, oneshot | Keeps an active infrastructure connection, joins a visible `!Totem`, or activates the local AP | NetworkManager profiles under `/etc/NetworkManager/system-connections/` |
| `totem-wifi-ap-idle.timer` / `.service` | root, timer + oneshot | Preserves an AP with associated stations; retries selection after ten empty minutes | Ephemeral idle start in `/run/totem-wifi-ap-idle` |
| `fips.service` | root | Mesh transport, authentication, routing, TUN, local DNS, control socket | `/etc/fips/fips.yaml`, `/etc/fips/fips.key` |
| `strfry.service` | `strfry` | Nostr relay, NIP-11, NIP-77/negentropy | `/etc/strfry.conf`, `/var/lib/strfry/` |
| `totemd.service` | `totem`, supplementary groups `fips`, `strfry` | FIPS watcher, NIP-11 prefilter, signed recognition, public web bind, loopback message bus, strfry runner access | `/etc/totemd/totemd.env`, `/etc/totemd/config.toml`; current encounter state is in memory |
| `totem.service` | `totem`, supplementary groups `gpio`, `i2c`, `spi` | FastAPI hardware service and lazy manager/driver lifecycle | `/etc/totem/totem.env`, `/var/lib/totem/storage` |

The systemd definitions are managed under `deploy/ansible/roles/`. The role
order is `base → network → fips → strfry → totemd → device_manager → verify`.

## Network surfaces

The port registry in `spec/07-conventions.md` pins the current deployment
defaults:

| Surface | Default bind | Exposure | Owner |
|---|---|---|---|
| Fallback AP gateway | `10.21.0.1/24` on `wlan0` | open `!Totem` Wi-Fi | NetworkManager |
| FIPS UDP transport | `0.0.0.0:2121` | physical network | FIPS |
| FIPS TCP transport | `0.0.0.0:8443` | physical network | FIPS |
| FIPS DNS responder | `[::1]:5354` | loopback | FIPS |
| FIPS control socket | `/run/fips/control.sock` | local Unix socket, `fips` group | FIPS |
| Relay WebSocket and NIP-11 | `[::]:7777` | IPv6 wildcard (including the FIPS overlay; IPv4-mapped behavior is host-dependent) | strfry |
| Public control plane and `/totem/challenge` | `[::]:8080` | IPv6 wildcard, dual-stack on the bench images | `totemd` |
| Totem message bus | `127.0.0.1:8081` | loopback only | `totemd` |
| Hardware API and WebSocket | `0.0.0.0:8000` | all interfaces | Python service |

The FIPS `.fips` responder is intentionally not installed into the system
resolver. Embedded applications query `[::1]:5354` directly. Do not infer
device-side resolver support from `.fips` resolution on a development host.

### Trust boundaries

- `totemd` keeps its message bus on loopback. `totemctl` is only an HTTP/SSE
  client of that bus; it is not a privileged back door.
- FIPS uses the filesystem permissions on its Unix socket for local control
  access. Its identity key remains root-owned and mode `0600`.
- systemd passes that key to unprivileged `totemd` as a private read-only
  credential for challenge signing. Inventory contains only the public
  identity, and the service account cannot read the source key directly.
- strfry is directly reachable on the mesh. Its write policy is currently
  empty in the bare-device template, so normal relay validation—not a Totem
  authorization plugin—governs writes.
- The Python API currently binds all interfaces, enables permissive CORS, and
  has no authentication layer. Treat port `8000` as a trusted-network or
  development surface until an explicit authorization boundary lands.
- The `totemd` public bind serves an embedded static Svelte app, limited
  public status/update projections, NIP-98 owner APIs, and the rate-limited
  responder at `/totem/challenge`. Owner mutations and the peer/activity
  stream require nonce-bound signatures; the first valid signer claims an
  unclaimed device. The generic bus remains inaccessible from this listener.

## Control and data flows

### Wi-Fi fallback

1. NetworkManager first attempts its ordinary configured infrastructure
   profiles.
2. At boot or after a `wlan0` disconnect, the fallback oneshot allows a short
   reconnect grace period.
3. If `!Totem` is visible, it activates the open `totem-peer` station profile.
4. Otherwise it waits a randomized interval, rescans to avoid simultaneous
   AP creation, and activates `totem-ap` at `10.21.0.1`.
5. A one-minute timer checks the kernel's associated-station table. Any station
   keeps the AP active; ten uninterrupted empty minutes restart this same
   selection cycle. Inspection failure preserves the AP and resets the timer.

### Mesh observation and bus events

1. FIPS authenticates direct peers and maintains mesh state.
2. Every `TOTEMD_FIPS_POLL_MS` milliseconds (default `2000`), `totemd`
   queries `show_peers` and `show_status` over the FIPS control socket.
3. `totemd` diffs the new npub-keyed snapshot against its in-memory state.
4. Arrivals emit `totem.peer.seen` and trigger a cached NIP-11 prefilter.
5. A matching `!Totem` name/public-key claim emits `totem.peer.candidate` and
   starts a fresh-nonce signed challenge against the peer's port `8080`.
6. A valid kind-27235 proof emits `totem.recognized` for the current FIPS
   encounter and starts an immediate policy-permitted bidirectional relay
   reconciliation.
7. Totemd repeats reconciliation five minutes after each round completes while
   the same encounter remains recognized; every `totem.sync.done` retains
   strfry's readable result and optional parsed set-difference counts.
8. Departure clears recognition, cancels a running child or interval wait, and
   emits `totem.peer.gone`.
9. Loopback consumers receive those pushes from `/bus/events`. The web app's
   public `/api/updates` strips payloads and invalidates `/api/status`; its
   owner-signed stream projects current peers/history plus future pushes. All
   push delivery remains lossy, so reconnecting consumers start from current
   state.

### Nostr storage and sync

strfry accepts standard Nostr WebSocket traffic and commits accepted events to
LMDB. The required artifact supports NIP-77 negentropy and the `strfry sync`
client. The Ansible contract verifies NIP-77 and the NIP-11 identity used by
totemd's implemented recognition/challenge loop. A 2026-08-20 live audit found
motown's original aarch64 artifact incompatible; it was replaced with strfry
master using NIP-77 protocol 0 and passed bidirectional reconciliation. `totemd` supervises the
unprivileged runner immediately and periodically after recognition, with
per-peer non-overlap, a per-round timeout, departure/shutdown cancellation,
and no extra database scan for its human-readable result.

### Hardware calls

1. A caller sends an HTTP request to the Python API.
2. The requested manager is initialized lazily on its first call.
3. A per-manager async lock serializes operations while the synchronous
   manager method runs in a thread pool.
4. The manager delegates to one selected driver. Mock display, NFC, and Wi-Fi
   drivers require explicit opt-in.
5. Initialization failures become HTTP `503`; operation failures become HTTP
   `502`.

The Python `EventManager` can broadcast typed device events over `/ws`, but
the built-in HTTP routes do not currently publish manager events. This event
channel and the Rust `totemd` bus are separate transports.

## Identity and addressing

FIPS uses a Nostr secp256k1 keypair as the device's mesh identity. From that
public key it derives a routing `node_addr` and an IPv6 ULA in `fd00::/8`.
The same identity anchors Totem recognition and NIP-11 metadata. Ansible's
bare strfry template fills `relay.info.pubkey` from the inventory's public
identity and verifies it against both NIP-11 and the signed challenge.

FIPS applies hop-by-hop Noise IK encryption between direct peers and
end-to-end Noise XK encryption between session endpoints. Intermediate mesh
nodes forward by derived routing address without receiving the endpoint
session plaintext.

## Implemented versus planned

| Capability | State in this revision |
|---|---|
| NetworkManager infrastructure/peer/AP fallback | Implemented; live host/peer validation passed in both directions on totem and motown |
| FIPS service, persistent identity, TUN, DNS, control socket | Implemented and deployment-verified |
| IPv6-capable strfry relay and NIP-77 advertisement | Implemented; protocol-0 capability is enforced by Ansible |
| `totemd` FIPS polling, peer snapshot, seen/gone pushes | Implemented |
| `totemctl` help/version/status/config/peers/history/events/generic call | Implemented |
| Python display/NFC/storage/network API | Implemented; hardware availability depends on the device |
| NIP-11 candidate probe and per-encounter signed Totem challenge | Implemented |
| Kind-3 contact writer | Bus message names reserved; writer returns “not implemented” |
| Automatic encounter sync supervisor | Implemented with immediate and five-minute periodic per-peer reconciliation |
| Web UI and NIP-98 administration | Read-only HTML landing implemented; authenticated controls planned |
| Happlet/NAP IPC runtime | Deferred beyond the v1 kernel |

## Source map

| Concern | Authoritative repository source |
|---|---|
| Product intent | `spec/01-overview.md` through `spec/10-control-plane.md` |
| Rust daemon and bus | `totemd/src/` |
| Python API and managers | `src/totem/api/`, `src/totem/managers/`, `src/totem/devices/` |
| Deployment and runtime configuration | `deploy/ansible/` |
| Display-specific wiring | `docs/hardware/display.md` |

Continue with the [`totemd` reference](/reference/totemd), the
[device-manager reference](/reference/device-manager), or the
[Ansible runbook](/operations/ansible).
