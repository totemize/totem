---
title: Totem state catalog and display projection
description: System, hardware, mesh, encounter, recognition, friendship, and sync states available to Totem display consumers
---

# Totem state catalog and display projection

A Totem is never in only one state. It can be booting while charging, have a
healthy relay but a degraded mesh, and synchronize with one peer while probing
another. The display should therefore consume a **snapshot of orthogonal state
axes** and project that snapshot into a scene. A single flat `TotemState` enum
would lose information and create impossible transition rules.

This catalog is based on the `totemd` branch at `a1a5979`, especially:

- `src/totem/screen/` for the current boot presentation;
- `src/totem/devices/` and `src/totem/api/` for hardware lifecycle and power;
- `totemd/src/` for FIPS health, peers, recognition, policy, and sync;
- `spec/01-overview.md` through `spec/10-control-plane.md` for product states
  that are specified but not implemented yet;
- `deploy/systemd/` for service ordering and restart behavior.

## Confidence labels

The tables use four labels so display work does not mistake an idea for a
current signal.

| Label | Meaning |
|---|---|
| **Observable** | Emitted or queryable by the current implementation. Exact wire values are shown in code formatting. |
| **Defined** | Present in an enum or specification, but not currently reached or exposed to the screen process. |
| **Derived** | A display-friendly state that can be computed from current fields without adding authority. |
| **Gap** | A meaningful product state that cannot yet be distinguished reliably; it needs a new field, event, or persisted record. |

## Flat state table

This is the compact index. The detailed sections below identify each value as
observable, defined, derived, or a gap.

| Axis | States |
|---|---|
| System lifecycle | `powered_off`, `powering_on`, `waiting_for_display_api`, `booting`, `ready`, `degraded`, `maintenance`, `updating`, `shutting_down`, `rebooting`, `failed` |
| systemd unit | `inactive`, `activating`, `active`, `deactivating`, `failed`, restart delay |
| Boot readiness (`device`, `fips`, `relay`, `totemd`) | waiting, ready, timed out, retrying |
| Screen | `booting`, `idle`, `new_peer`, `existing_peer`, `error`, `synchronizing` |
| Driver | `new`, `ready`, `mock`, `closed`, `failed` |
| Display activity | idle, rendering, refreshing, sleeping, waking, refresh failed |
| NFC activity | idle, waiting for card, card present, reading, writing, completed, error |
| Storage activity | idle, reading, writing, near capacity, full, read-only, I/O error |
| Network activity | disconnected, scanning, connecting, station connected, hotspot active, disconnecting, failed |
| UPS telemetry | unavailable, readable, read error |
| Power source | `external_power`, `on_battery`, `source_unknown`, `telemetry_unavailable` |
| Charge band | `full`, `high`, `normal`, `low`, `critical`, `empty` |
| Charge flow | `charging`, `discharging`, `near_zero_current`, `critical_shutdown_pending`, `safe_to_remove`, `charge_complete` |
| Temperature | unknown, normal, warm, hot, throttled, thermal shutdown imminent |
| Input supply | normal, current undervoltage, historical undervoltage/throttle |
| CPU | idle, normal, busy, saturated |
| Memory | normal, pressure, swapping, OOM/recovering |
| Filesystem | read-write, low space, critical, full, read-only, I/O error |
| Clock | unknown/unset, plausible but unsynchronized, synchronized |
| Kernel/device tree | normal, required interface absent, driver/module error |
| Wi-Fi role | `infra_station`, `ap_host`, `disconnected`, `configuring`, `failed` |
| BLE | off, beaconing/discovering, linked, error |
| FIPS overlay | unavailable, available without upstream, internet-reachable |
| Upstream | absent, local-only, internet-reachable |
| Guest AP | no guests, one guest, multiple guests |
| Mesh mood | `alone`, `peer_nearby`, `small_mesh`, `busy_mesh`, `mesh_degraded` |
| `totemd` | `starting`, `running`, `running_fips_degraded`, `shutting_down`, `failed_config`, `failed_identity`, `failed_bind`, `failed_server`, `restarting` |
| Identity | `unprovisioned`, `identity_loaded`, `identity_unknown`, `declaration_valid`, `declaration_missing`, `identity_mismatch`, `key_rotation_pending` |
| Bus consumer | `disconnected`, `connecting`, `subscribed`, `lagged`, `reconnecting`, `reconciling` |
| Peer encounter | `absent`, `seen`, `probe_disabled`, `probe_pending`, `not_a_totem`, `unreachable`, `candidate`, `challenge_pending`, `challenge_failed`, `challenge_stale`, `recognized`, `departing`, `gone` |
| Relationship | `stranger`, `following`, `followed_by`, `friend`, `approval_pending`, `publishing_follow`, `befriend_failed`, `befriended` |
| Sync | `null`, `running`, `succeeded`, `failed`, `timed_out`, `cancelled`, `eligible_waiting`, `policy_blocked`, `friends_only_blocked`, `interrupted_resumable` |
| Relay/content | unavailable, listening, client connected/disconnected, note received/published, sync import/export active/result |
| Human activity | guest joined/left, owner authenticated, policy changed, friendship approved, NFC presented/read/written |
| `totemd` event | `totem.peer.seen`, `totem.peer.gone`, `totem.peer.candidate`, `totem.recognized`, `totem.sync.started`, `totem.sync.done`, `totem.befriended` |

Axes combine freely: charging while syncing is two simultaneous states, not a
new compound state.

## 1. System lifecycle

These are the recommended device-wide lifecycle states. Only part of this
axis is currently available to the display process.

| State | Evidence | Meaning and transition |
|---|---|---|
| `powered_off` | Derived | No process can report it. E-ink retains the last frame, so a deliberate shutdown frame is the only visible evidence. |
| `powering_on` | Gap | Firmware/kernel/userspace are starting but `totem-screen` has not run. There is no userspace signal yet. |
| `waiting_for_display_api` | Observable | `totem-screen` is active and polling the Python device API, but has not rendered the splash. |
| `booting` | Observable | `ScreenState.BOOTING`; the splash or readiness checklist is being rendered. |
| `ready` | Observable | The boot controller reached `ScreenState.IDLE` after all four readiness checks passed. |
| `degraded` | Derived | The device remains useful but one or more required services or hardware capabilities are unhealthy. Continuous post-boot monitoring is not implemented yet. |
| `maintenance` / `updating` | Gap | Deployment, migration, or operator maintenance is in progress. Ansible/systemd perform these operations but publish no presentation signal. |
| `shutting_down` | Gap | systemd is stopping services and `totemd` is cancelling sync children. No typed screen event exists. |
| `rebooting` | Gap | A shutdown whose intended successor is a new boot. Not distinguishable from shutdown today. |
| `failed` | Derived | A required unit has failed or is crash-looping. systemd knows this; the control-plane snapshot does not. |

Every systemd-managed service can also be in the standard unit lifecycle:
`inactive`, `activating`, `active`, `deactivating`, `failed`, and an
auto-restart delay. These should remain diagnostic details beneath the
device-wide lifecycle rather than becoming top-level display scenes.

### Boot readiness substates

The boot checklist independently probes four useful interfaces:

| Key | Ready when | Current presentation |
|---|---|---|
| `device` | Python device API `/health` responds | `Device API` checkmark |
| `fips` | `fipsctl show status` reports `state=running` and `tun_state=active` | `FIPS mesh` checkmark |
| `relay` | TCP connection to `[::1]:7777` succeeds | `Nostr relay` checkmark |
| `totemd` | `totemctl status` returns `ok=true` | `Control plane` checkmark |

The readiness vector has 16 theoretical subsets. The controller renders a
new frame when it first observes a service as ready, latches that service,
and never removes a checkmark. It stops monitoring after reaching idle.
Consequently, post-boot service loss is currently invisible to the screen.

`totem-screen.service` is `Type=notify`, starts after `totem.service`, and is
ordered before FIPS, strfry, and totemd. Its 120-second systemd start timeout
and `Restart=on-failure` create additional real states: a boot that never
finishes, a retained partial checklist, and an automatic screen-process retry.

## 2. Current presentation states

`ScreenState` defines these exact values:

| Value | Status | Current behavior |
|---|---|---|
| `booting` | Observable | Used for the splash and readiness checklist. |
| `idle` | Observable | Used after boot; currently renders `(^_^)`. |
| `new_peer` | Defined | Renderer accepts it, but no control-plane event selects it. |
| `existing_peer` | Defined | Renderer accepts it, but no durable encounter history can classify a peer reliably. |
| `error` | Defined | Renderer accepts it, but boot/runtime failures do not transition to it. |
| `synchronizing` | Defined | Renderer accepts it, but sync events are not consumed by `totem-screen`. |

Only `booting` and `idle` are reached by `ScreenController.boot()`. The other
values currently render a centered headline through the renderer's generic
branch. They are presentation vocabulary, not yet state authority.

## 3. Service and process health

The display should track each process independently and derive aggregate
health from required capabilities.

| Service | Useful states | Current observability |
|---|---|---|
| `totem.service` | starting, HTTP-ready, healthy/no managers opened, manager init failure, operation failure, stopping, failed/restarting | `/health` proves only the API process. It returns `initialized_managers`; initialization and operation failures surface as HTTP 503 and 502. |
| `totem-screen.service` | disabled/absent display, starting, refreshing, idle, failed/restarting, stopping | systemd only; the screen does not publish its own status. |
| `fips.service` | starting, running/TUN active, running without TUN, degraded, stopped, failed/restarting | Boot probe sees `state` and `tun_state`; `totemd` only exposes whether its latest control-socket poll succeeded. |
| `strfry.service` | starting, listening, unavailable, failed/restarting, accepting clients, storage error | Boot probe sees only whether port 7777 accepts TCP. |
| `totemd.service` | validating config, loading key, binding, running, FIPS-watcher degraded, shutting down, failed/restarting | Bus reachability and `totem.status.get` prove running; failure detail otherwise lives in systemd/journald. |

`totemd` fails fast before serving if its config is malformed, its signing key
is missing/invalid, or either HTTP listener cannot bind. During graceful
shutdown it aborts the FIPS watcher, cancels active sync children, waits up to
five seconds for them, drains the public and loopback servers, and exits.

## 4. Hardware and driver lifecycle

Every device driver shares the exact `DriverState` vocabulary:

| Value | Status | Meaning |
|---|---|---|
| `new` | Observable | Driver object exists but is not initialized. |
| `ready` | Observable | Real hardware initialized successfully. |
| `mock` | Observable | Explicitly allowed mock/non-hardware transport initialized. |
| `closed` | Observable | Resources were released and the driver was marked closed. |
| `failed` | Defined | Reserved in the enum, but the base `health()` implementation never emits it. Initialization failures generally raise and the API returns 503. |

The generic `DriverHealth` also contains `initialized`, `is_mock`, optional
`message`, optional `details`, and a derived `operational` boolean. The API
does not currently expose this health object as a route.

Peripherals add activity states above the driver lifecycle:

| Peripheral | Potential activity states | Signal status |
|---|---|---|
| Display | idle, rendering, refreshing, sleeping, waking, refresh failed | Gap: operations are serialized, but no state is published. |
| NFC | idle, waiting for card, card present, reading, writing, completed, error | Gap: no built-in route publishes device events. |
| Storage | idle, reading, writing, near capacity, full, read-only, I/O error | Gap: reads/writes exist; capacity and health do not. |
| Network | disconnected, scanning, connecting, station connected, hotspot active, disconnecting, failed | Partly observable only through in-process `get_wifi_status()`; not exposed over HTTP or the totem bus. |
| UPS | unavailable, readable, read error plus the power states below | Observable through `/ups/status` when a configured manager initializes. |

The Python `EventManager` already reserves device event types
`state_change`, `command_completed`, `error`, `data_available`, and
`hardware_event` for display, NFC, storage, network, and UPS devices. No
built-in manager or route publishes them in this revision.

## 5. Power states

The UPS snapshot exposes continuous facts rather than a power-state enum:

- `battery_percent`: `0.0` through `100.0`;
- `voltage_volts`;
- signed `current_amps`;
- `power_plugged`: `true`, `false`, or `null` when the board has no direct
  external-power signal;
- `model`.

The exact observable power-source states are therefore:

| State | Expression |
|---|---|
| `external_power` | `power_plugged == true` |
| `on_battery` | `power_plugged == false` |
| `source_unknown` | `power_plugged == null` |
| `telemetry_unavailable` | UPS not configured, initialization failed, or read failed |

For presentation, derive configurable charge bands rather than hard-coding
them into drivers: `full`, `high`, `normal`, `low`, `critical`, and `empty`.
Also derive `charging`, `discharging`, and `near_zero_current` only after each
UPS driver has a documented current-direction convention and a noise
threshold. The current code preserves the board's signed reading but does not
normalize its meaning across models.

Useful future system states are `critical_shutdown_pending`, `safe_to_remove`
and `charge_complete`; none is currently authoritative.

## 6. Host and board health

Linux and Raspberry Pi expose additional system-health axes that are not yet
part of either local API. They matter because the device can remain partially
useful while degraded.

| Axis | Potential states | Current status |
|---|---|---|
| Temperature | unknown, normal, warm, hot, throttled, thermal shutdown imminent | Gap: no normalized temperature or throttle field |
| Input supply | normal, current undervoltage, historical undervoltage/throttle | Gap: UPS source telemetry does not replace the Pi firmware's supply/throttle flags |
| CPU | idle, normal, busy, saturated | Gap: no load policy or snapshot field |
| Memory | normal, pressure, swapping, OOM/recovering | Gap |
| Root/data filesystem | read-write, low space, critical, full, read-only, I/O error | Gap; especially important for the relay LMDB |
| Clock | unknown/unset, plausible but unsynchronized, synchronized | Gap; recognition deliberately never requires wall-clock validity |
| Kernel/device tree | normal, required interface absent, driver/module error | Partly visible only as downstream hardware initialization failure |

Thresholds for warm/hot, load, memory pressure, and free space belong in
device policy. A presentation layer should not infer them independently from
raw Linux numbers.

## 7. Radio, network, and reachability

These are separate axes. BLE is an additional transport and should not be
folded into the Wi-Fi role.

### Wi-Fi role

| State | Status | Meaning |
|---|---|---|
| `infra_station` | Defined by spec | Joined to infrastructure Wi-Fi; FIPS can discover over shared L2; guests use that network. |
| `ap_host` | Defined by spec | Emitting the `!Totem` AP for guests and possible Totem stations. |
| `disconnected` | Observable in driver | Neither station nor hotspot is active. |
| `configuring` | Gap | Scan/connect/hotspot operation is in progress but no event is published. |
| `failed` | Observable as operation error | `nmcli` failed or status could not be read. |

Real Wi-Fi drivers return NetworkManager's raw device state and connection
name; the API does not expose that getter. The mock driver can additionally
report station signal strength or hotspot client count.

### Other reach axes

| Axis | Values |
|---|---|
| BLE transport | off, beaconing/discovering, linked, error; specified for v1.5 but not owned by Totem code |
| FIPS IP overlay | unavailable, available without upstream reach, reachable over upstream internet |
| Upstream connectivity | absent, local-only, internet-reachable |
| Guest AP activity | no guests, one guest, multiple guests; Gap: no production signal |

## 8. FIPS and mesh state

`totem.status.get` exposes this FIPS projection:

| Field/state | Meaning |
|---|---|
| `fips.connected=false`, no prior success | `totemd` has not completed a successful control-socket poll. |
| `fips.connected=true` | The latest `show_peers` and `show_status` poll succeeded. It does **not** mean another peer is connected. |
| `fips.connected=false`, `last_error` set | The watcher is degraded; its last peer snapshot remains cached. |
| `fips.npub=null` | Local identity has not yet arrived through a successful poll. |
| `fips.mesh_size=0` | No successful estimate yet, or FIPS reported zero. |
| `peers=0` | No directly authenticated peers in the current snapshot. |
| `peers>0` | One or more current authenticated FIPS peers. |
| `mesh_size>1` | FIPS estimates a multi-node mesh, which may include nodes that are not direct peers. |

Full FIPS health additionally distinguishes `state=running` and
`tun_state=active`. A known runtime failure can leave FIPS latched degraded
with `fips0` absent, so these states must not be inferred from control-socket
reachability alone.

Useful display-derived mesh moods include `alone`, `peer_nearby`,
`small_mesh`, `busy_mesh`, and `mesh_degraded`. Their numeric thresholds are
presentation policy, not protocol state.

## 9. Control-plane lifecycle, identity, and policy

### Daemon lifecycle

| State | Evidence |
|---|---|
| `starting` | Process launched; config/key/listeners are not all ready. |
| `running` | Bus responds and both public/bus listeners are serving. |
| `running_fips_degraded` | Bus responds but `fips.connected=false`. |
| `shutting_down` | Signal received; FIPS watcher aborted and syncs cancelling. Gap: not queryable once shutdown begins. |
| `failed_config` | Present config is unreadable, malformed, has unknown keys, or invalid values. |
| `failed_identity` | Signing credential cannot be read or parsed. |
| `failed_bind` / `failed_server` | Listener bind or serving failed. |
| `restarting` | Derived from the systemd `Restart=on-failure` delay. |

### Self-identity and provisioning

| State | Meaning | Current status |
|---|---|---|
| `unprovisioned` | Persistent FIPS/device identity is absent | FIPS and `totemd` fail rather than exposing a typed state |
| `identity_loaded` | FIPS is persistent and `totemd` loaded the same signing key | Indirectly verifiable through FIPS status and challenge output |
| `identity_unknown` | No successful FIPS poll has populated `fips.npub` | Observable as `fips.npub=null` |
| `declaration_valid` | NIP-11 `!Totem` marker and pubkey match the device identity | Deployment verifier checks it; local status does not |
| `declaration_missing` / `identity_mismatch` | Relay is not recognizable as this Totem | Gap in runtime status; peers will grade it non-Totem |
| `key_rotation_pending` | Operator intends to change identity | Open design question; no workflow/state exists |

### Engagement policy

These policy values change which encounter states are reachable:

| Axis | Values | Effect |
|---|---|---|
| NIP-11 probing | `probe=true` / `false` | Disabled probing leaves every peer ungraded and unrecognized. |
| Negative verdict cache | `verdict_ttl_hours` | Controls retry of `not_totem` and `unreachable`; candidates remain cached for the daemon lifetime. |
| Befriend | `auto`, `ask`, `never` | Specified publication behavior after recognition. Writer/pending approval are not implemented. |
| Sync | `sync=true` / `false` | All recognized Totems versus recognized friends only. The current friend set is empty because its reader is not implemented. |

### Bus consumer state

A display consumer also needs its own connection lifecycle:
`disconnected`, `connecting`, `subscribed`, `lagged`, `reconnecting`, and
`reconciling`. The SSE channel is lossy and has capacity 256. Every connect
or reconnect must query `totem.status.get` and `totem.peers.get`; pushes are
notifications, never the source of truth.

## 10. Per-peer encounter ladder

Each authenticated peer has an independent current-encounter state. The best
current source is `totem.peers.get`, reconciled with pushes.

| Semantic state | Current fields/events | Confidence |
|---|---|---|
| `absent` | Peer not in snapshot | Observable |
| `seen` | Entry exists; `totem.peer.seen` was emitted | Observable |
| `probe_disabled` | `probe_verdict=null` indefinitely while global `probe=false` | Derived |
| `probe_pending` | `probe_verdict=null`, probing enabled, not recognized | Derived, but not distinguishable from a task that failed before caching |
| `not_a_totem` | `probe_verdict=not_totem` | Observable |
| `unreachable` | `probe_verdict=unreachable` | Observable |
| `candidate` | `probe_verdict=candidate`; `totem.peer.candidate` emitted | Observable |
| `challenge_pending` | Candidate and `recognized=false` immediately after the candidate push | Derived transient |
| `challenge_failed` | Challenge task completed with an error | Gap: logged only; fields look like a candidate still pending |
| `challenge_stale` | Proof returned after the peer's encounter token changed | Gap: logged only and discarded |
| `recognized` | `recognized=true`; `totem.recognized` emitted | Observable for this encounter only |
| `departing` | Prior peer disappears; active sync is being cancelled | Derived transient |
| `gone` | `totem.peer.gone` emitted; peer removed and recognition cleared | Observable push; absent from the next snapshot |

The progression is:

```text
absent
  -> seen
  -> probe_pending
  -> not_a_totem | unreachable | candidate
  -> challenge_pending
  -> recognized | challenge_failed
  -> gone
```

Candidate grades may be reused across encounters, but the signed challenge is
always per encounter. `first_seen` is the in-memory encounter token, not a
durable “first time ever” timestamp.

### New versus returning peers

`ScreenState.NEW_PEER` and `EXISTING_PEER` cannot yet be selected reliably.
Timestamps, verdict caches, counters, and recognition reset on `totemd`
restart; gone peers leave the current peer map; and the specified encounter
log is not implemented. A persisted encounter history should expose an
explicit `encounter_ordinal` or `known_before` field rather than asking the
display to guess from cache state.

## 11. Relationship and friendship state

The specification defines relationships through NIP-02 kind-3 events. These
states are identity-scoped and persist beyond an encounter:

| State | Meaning | Current status |
|---|---|---|
| `stranger` | Neither side follows the other | Specified, not queryable |
| `following` | This Totem follows the peer | Specified, writer not implemented |
| `followed_by` | Peer follows this Totem | Specified, reader not implemented |
| `friend` | Mutual follows | Specified, reader not implemented |
| `approval_pending` | `befriend=ask` and owner decision is pending | Specified, pending store/UI not implemented |
| `publishing_follow` | Kind-3 read-modify-sign-write in progress | Gap |
| `befriend_failed` | Kind-3 publication failed | Gap |
| `befriended` | Publication succeeded; `totem.befriended` | Event name reserved by spec, never emitted in this revision |

The global policy value (`auto`, `ask`, or `never`) is observable now, but it
must not be presented as if a per-peer relationship had already changed.

## 12. Per-peer synchronization state

`sync_state` has these exact current-encounter values:

| Value | Meaning | Terminal? |
|---|---|---|
| `null` | No job recorded for this encounter. This can mean not yet started, policy-blocked, unrecognized, or invalid address. | ambiguous |
| `running` | Bidirectional `strfry sync --dir=both` child is active. | no |
| `succeeded` | Child exited successfully. | yes |
| `failed` | Spawn failed, wait failed, or child exited non-zero. | yes |
| `timed_out` | Bounded runtime elapsed; child was killed. | yes |
| `cancelled` | Departure, daemon shutdown, or replacement encounter cancelled the child. | yes |

For non-null jobs the peer snapshot also exposes elapsed/final duration,
optional exit code, and optional error. `totem.sync.started` and
`totem.sync.done` carry the encounter token and `direction=both`; the done
event adds `outcome`, duration, exit code, and error.

Useful semantic states that are not represented distinctly are
`eligible_waiting`, `policy_blocked`, `friends_only_blocked`, and
`interrupted_resumable`. NIP-77 makes a later attempt resumable, but
resumability is a property of reconciliation rather than another child
process state.

Multiple peers can be `running` simultaneously. The display should choose
between an aggregate scene (“syncing with 3 Totems”) and a rotating focus;
it must not assume a single global sync.

## 13. Relay, content, and storage state

Current authority is sparse:

| State | Current signal |
|---|---|
| Relay unavailable/listening | Boot TCP probe only |
| Encounter sync active/result | Per-peer sync state and pushes |
| Relay event count | Specified in `totem.status.get`, not implemented |
| Relay clients connected | Gap |
| Note received/published | Gap |
| Events imported/exported by sync | Reserved in spec when runner exposes reliable counts; not present now |
| Storage usage/remaining | Specified in status/user stories, not implemented |
| Storage near-full/full/read-only/error | Gap |
| Moderation/deletion activity | Future owner controls |

These missing signals are high-value for an entertaining display: “carrying
42 notes,” “received a new note,” and “traded 7 notes” are more legible to a
human than a successful process exit.

## 14. Human and client activity

The product defines owner, guest, and authenticated FIPS-peer roles, but the
runtime does not publish client-presence events. Potential activity states
include:

| Activity | Status |
|---|---|
| Guest joined/left the `!Totem` AP | Gap |
| Nostr client connected/disconnected from the relay | Gap |
| Guest read or posted a note | Gap; relay instrumentation needed |
| Authenticated FIPS user reached the Totem | FIPS sees the peer, but Totem cannot currently distinguish human node from ordinary non-Totem node beyond the failed/negative Totem probe |
| Owner authenticated to the web app | NIP-98 claim and owner-signed state streaming are implemented; opening owner mode has no dedicated push |
| Owner changed policy or approved friendship | Policy changes are implemented and emit `totem.config.changed`; friendship approval remains a gap |
| NFC card presented/read/written | Driver operations exist; no published event |

These activities should be transient overlays, not device-wide lifecycle
states.

## 15. Current event vocabulary

The implemented `totemd` pushes are:

| Event | Trigger |
|---|---|
| `totem.peer.seen` | Authenticated FIPS peer appeared |
| `totem.peer.gone` | Peer disappeared |
| `totem.peer.candidate` | NIP-11 marker and identity claim matched |
| `totem.recognized` | Signed challenge passed for the current encounter |
| `totem.sync.started` | Policy-permitted job was reserved |
| `totem.sync.done` | Job succeeded, failed, timed out, or was cancelled |
| `totem.owner.claimed` | The first valid signer became the durable owner |
| `totem.metadata.changed` | A device-signed kind-0 profile was imported |
| `totem.config.changed` | Owner policy overrides were persisted and applied |

The spec additionally reserves `totem.befriended`. The Python device-event
channel reserves generic hardware events but currently publishes none.

## 16. Display projection

Keep authority and presentation separate. A useful normalized snapshot is:

```text
TotemSnapshot
  lifecycle
  services[device, screen, fips, relay, totemd]
  drivers[display, nfc, storage, network, ups]
  power
  radio
  mesh
  peers[]
  relay
  storage
  active_human_events[]
  alerts[]
```

The renderer then selects three layers:

1. **Base scene** — boot, idle, maintenance, shutdown, or unavailable.
2. **Activity scene** — peer encounter, recognition, sync, note/NFC activity.
3. **Persistent badges** — charge, low battery, Wi-Fi role, mesh size, and
   degraded-service indicators.

This allows “synchronizing while charging with one unhealthy optional
peripheral” without inventing a special compound enum value.

### Recommended arbitration order

Highest priority wins the main scene; lower-priority facts remain badges when
possible.

| Priority | Scene class | Examples |
|---:|---|---|
| 100 | Safe shutdown / power emergency | critical battery, shutting down, “good night” retained frame |
| 90 | Unusable or action-required fault | display/API failure, relay down, identity/config failure |
| 80 | Boot or maintenance gate | splash, readiness checklist, updating |
| 70 | Social payoff | new Totem recognized, returning Totem, befriended |
| 60 | Active exchange | sync running, note received, NFC activity |
| 50 | Transient result | sync success/failure/timeout/cancel, peer gone |
| 10 | Ambient idle | face/lore rotation with battery and mesh badges |

Degraded-but-usable conditions should usually become badges or periodically
interleaved scenes; otherwise one weak subsystem can permanently suppress the
fun social behavior.

### Suggested playful mappings

These are presentation copy, not protocol state:

| Semantic state | Possible treatment |
|---|---|
| Alone and idle | Rotate low-refresh faces, lore, note count, and battery/mesh badges |
| Peer seen | “Something rustled nearby…” |
| Candidate | “Are you a Totem?” |
| Newly recognized | celebratory face and “New Totem!” |
| Returning recognized | familiar face and “You again!” |
| Sync running | “Trading secrets…” or “Swapping notes…” |
| Sync succeeded | “Trade complete” plus event counts when available |
| Sync timed out/cancelled | “Until next time” rather than a hard error |
| Non-Totem FIPS peer | normally silent; optional curious ambient reaction |
| Charging | feeding/eating badge or face |
| Low battery | sleepy face; critical becomes persistent/actionable |
| Mesh degraded | small warning badge while useful local functions continue |

### E-ink scheduling rules

- Reconcile snapshots after every SSE connection/reconnection before choosing
  a frame.
- Debounce the two-second FIPS polling burst so `seen`, `candidate`,
  `recognized`, and `sync.started` do not cause four immediate full refreshes.
- Give social payoff frames a minimum dwell, then transition to the newest
  authoritative activity.
- Coalesce simultaneous peer activity into an aggregate frame or a bounded
  queue.
- Rate-limit ambient changes and prefer badges for slowly changing values.
- Render shutdown intent before services disappear; an e-ink panel will keep
  that frame without power.
- On screen-process restart, rebuild from snapshots rather than replaying old
  pushes.

## 17. Signal gaps to close before the full display can ship

Prioritize these additions:

1. **Continuous service snapshot.** Keep monitoring after boot and expose
   required/optional service health rather than latching readiness forever.
2. **Durable encounter history.** Implement the specified encounter log and
   expose `known_before`/`encounter_ordinal` so new versus returning Totems is
   authoritative.
3. **Explicit challenge state.** Add pending/passed/failed/stale outcome and a
   failure event; a candidate currently looks pending forever after failure.
4. **Relationship state.** Implement the kind-3 reader/writer, owner-approval
   pending state, and success/failure events.
5. **Sync eligibility reason.** Distinguish not-started from policy-blocked
   and invalid-address states instead of overloading `null`.
6. **Power normalization.** Expose stable power-source/charge-mode semantics
   and configurable low/critical thresholds.
7. **Host-health normalization.** Expose board temperature/throttle flags,
   resource pressure, clock validity, and filesystem capacity with
   device-policy thresholds.
8. **Relay/storage facts.** Add event counts, event deltas per sync, client
   activity, and remaining storage.
9. **System intent.** Publish boot-complete, updating, shutdown, and reboot
   intent early enough for the e-ink process to render them.
10. **Hardware event bridge.** Connect the Python device-event channel to the
   control-plane bus or define one authoritative local snapshot surface.
11. **Sequencing metadata.** Give pushes a timestamp/sequence and retain
    snapshot authority so the display can coalesce without inventing order.

Until these land, a truthful first interactive version can already implement
boot progress, idle, FIPS health/mesh badges, peer seen/candidate/recognized,
all five sync outcomes, peer departure, UPS telemetry, and generic degraded
service screens.
