---
title: totemd control plane, CLI, and message bus
description: Daemon policy, signed recognition, totemctl commands, bus envelopes, and FIPS polling
---

<!-- generated-by: gsd-doc-writer -->

# `totemd` CLI and message bus

`totemd` is one Rust binary with two faces:

- `totemd serve` starts the control-plane daemon.
- `totemctl …` runs a synchronous client of the daemon's loopback HTTP/SSE
  bus. Deployment creates `totemctl` as a symlink to the same binary.

The implemented encounter ladder watches authenticated FIPS peers, applies a
cached NIP-11 identity prefilter, and proves candidates with a signed
per-encounter challenge, then supervises immediate and five-minute periodic
bidirectional relay reconciliation while peers remain recognized. The public
web app also supports first-signer claim, owner-authenticated policy changes,
and device-signed kind-0 metadata. Kind-3 contact-list writes remain the next
control-plane slice.

## Daemon command

```text
totemd serve
```

Starting `totemd` without a mode, or with a mode other than `serve` or
`totemctl`, exits with status `2` and prints usage.

### Environment

| Variable | Default | Effect |
|---|---|---|
| `TOTEMD_WEB_ADDR` | `[::]:8080` | Public HTTP listener for the web app, owner API, and `/totem/challenge`. The IPv6 wildcard is required by the FIPS overlay. |
| `TOTEMD_BUS_ADDR` | `127.0.0.1:8081` | Bus listener used by both daemon and `totemctl`. Keep it loopback-only. |
| `TOTEMD_FIPS_SOCK` | `/run/fips/control.sock` | FIPS Unix control-socket path. |
| `TOTEMD_FIPS_POLL_MS` | `2000` | FIPS status/peer polling interval in milliseconds. Invalid values fall back to `2000`. |
| `TOTEMD_CONFIG` | `/etc/totemd/config.toml` | Deployment fallback file. Missing means defaults; malformed content stops startup. |
| `TOTEMD_STATE` | `/var/lib/totemd/state.toml` | Durable owner and policy-override state. Malformed or unsupported state stops startup. |
| `TOTEMD_NIP11_NAME_PATH` | `/var/lib/totemd/nip11-name` | Derived public name read by strfry; primarily overridable for tests. |
| `TOTEMD_STRFRY_RUNNER` | `/usr/local/libexec/totem-strfry` | Trusted local relay scan/import runner; primarily overridable for tests. |
| `TOTEMD_KEY_PATH` | systemd credential `fips.key`, else `/etc/fips/fips.key` | Explicit challenge-signing key override, primarily for local tests/development. |
| `TOTEMD_SYNC_INTERVAL_SECS` | `300` | Delay after one reconciliation completes before the next round for the same encounter. Invalid or zero values use the default. |
| `TOTEMD_SYNC_TIMEOUT_SECS` | `300` | Maximum runtime of one reconciliation round before the child is killed. Invalid or zero values use the default. |
| `RUST_LOG` | `info` directive added | tracing filter for daemon logs. |

The deployed defaults live in `/etc/totemd/totemd.env`; operator policy lives
in `/etc/totemd/config.toml`. The service runs `/usr/local/bin/totemd serve`
as user `totem` with supplementary group `fips`. systemd
`LoadCredential=fips.key:/etc/fips/fips.key` supplies a private read-only key
to the unprivileged daemon without loosening the root-owned source.

### Fallback and effective policy

```toml
[device]
name = "Totem"

[net]
probe = true
verdict_ttl_hours = 24

[policy]
befriend = "ask"
sync = true
```

`device.name` is the fallback until the relay contains a valid kind-0 event
signed by the device identity. The effective name is mirrored into strfry's
NIP-11 document without restarting the relay. `probe` enables the read-only
NIP-11 prefilter. Positive candidates remain
cached for the daemon lifetime; `not_totem` and `unreachable` grades are
retried after `verdict_ttl_hours`. `befriend` accepts `auto`, `ask`, or
`never`. `sync = true` reconciles with every recognized Totem; `false`
restricts reconciliation to recognized peers already known as friends. Until
the kind-3 reader lands, that friends-only set is empty. Eligible encounters
reconcile immediately and then every five minutes without requiring a
reconnect.

## `totemctl` reference

```text
totemctl help
totemctl version
totemctl status
totemctl config
totemctl peers
totemctl history
totemctl events
totemctl call <type> [json-object]
```

| Command | Bus operation | Output |
|---|---|---|
| `help`, `-h`, `--help` | none | Usage and command descriptions. |
| `version`, `-V`, `--version` | none | `totemctl` package version. |
| `status` | `totem.status.get` | Pretty-printed result object with daemon, FIPS, peer, and push-counter state. |
| `config` | `totem.config.get` | Effective operator engagement policy. |
| `peers` | `totem.peers.get` | Pretty-printed result object containing the current peer array. |
| `history` | `totem.events.get` | Latest 256 pushes from the current daemon run, oldest first; exits after printing. |
| `events` | `GET /bus/events` | Long-running future-only SSE stream; confirms the connection on stderr, prints non-empty `event:` and `data:` lines, and suppresses keep-alive comments. |
| `call` | caller-selected type | Generic escape hatch for any current or future bus message. |

The client reads `TOTEMD_BUS_ADDR`, so it can target a non-default local bind:

```bash
TOTEMD_BUS_ADDR=127.0.0.1:9081 totemctl status
```

### Generic calls

The optional payload must be one JSON object. `totemctl` overwrites its
`type` field with the command-line type; all other properties, including
`id`, are preserved.

```bash
totemctl call totem.peers.get
totemctl call totem.status.get '{"id":"operator-42"}'
totemctl call totem.contacts.add '{"id":"c1","npub":"npub1…"}'
```

The last command currently returns an application-level error because the
contacts writer is not implemented.

### Exit behavior

| Exit | Meaning |
|---|---|
| `0` | Request was transported and its JSON result printed, or an event stream ended normally. An application result with `"ok": false` still exits `0`; inspect the JSON. |
| `1` | The bus could not be reached. |
| `2` | Unknown/missing command, missing call type, malformed JSON, or a non-object call payload. |

## Public web app and owner API

`GET /` returns the static Svelte application embedded in the totemd binary.
Its HTML, CSS, and application JavaScript are built in `webapp/`; devices need
no Node runtime or loose asset directory. The app loads aggregate state from a
deliberately limited same-origin API and never connects to the generic bus.
The CSP permits Chrome/Firefox extension schemes required by late-injected
NIP-07 providers. Standard `window.nostr` providers work unchanged; when
nos2x's manifest blocks its own provider resource on private-LAN HTTP origins,
the app falls back to its already-injected content-script message bridge. An
early-development nsec escape hatch lazily loads a pinned `nostr-tools` bundle:
the secret stays in page memory, is never sent or persisted, and its byte array
is cleared on logout/navigation. There are no external runtime assets.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | Public profile, request-host relay URL, effective policy, and aggregate daemon/FIPS status. |
| `GET` | `/api/updates` | Public SSE invalidations with empty payloads; clients refetch `/api/status`. |
| `POST` | `/api/auth/challenge` | Issue a one-use nonce bound to one supported target, method, and exact body hash. |
| `GET` | `/api/owner` | Return only `claimed: true|false`. |
| `POST` | `/api/owner/claim` | Atomically persist the first valid signer as owner. |
| `GET` | `/api/owner/events` | Owner-signed current status, peer snapshot, and bounded history followed by future typed pushes. |
| `GET`, `PUT` | `/api/metadata` | Read effective metadata or publish device-signed kind 0 with owner authorization. |
| `GET`, `PUT` | `/api/config` | Read effective policy or persist owner policy overrides. |

Authorized requests use `Authorization: Nostr <base64-event>`. Kind 27235
must contain exact `nonce`, `u`, `method`, and SHA-256 `payload` tags. Nonces
expire after five minutes and are consumed once; `created_at` is not an
acceptance clock. The owner event stream hashes an empty body and one signature
authenticates only that connection; a reconnect requires another signature.
There is no browser session or bearer token. The initial first-signer claim
assumes a trusted bootstrap network.

## Bus transport

The bus is plain HTTP on the configured loopback address.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/bus` | One JSON request and one JSON result. |
| `GET` | `/bus/events` | Unsolicited pushes as server-sent events (SSE). |

The public listener on port `8080` is separate. Posting `/bus` there does not
work, and the loopback bus should not be exposed through a reverse proxy.

### Request/result envelope

Requests follow the NIP-5D-shaped convention defined in
`spec/07-conventions.md`:

```json
{
  "type": "totem.status.get",
  "id": "req-1"
}
```

Results use `<request-type>.result`, echo `id` when supplied, and include an
application `ok` flag:

```json
{
  "type": "totem.status.get.result",
  "id": "req-1",
  "ok": true,
  "status": {}
}
```

The `id` is optional in the current dispatcher, but clients should provide a
stable per-request identifier so asynchronous integrations can correlate
results consistently.

Malformed POST bodies produce this transport-level response rather than a
typed result:

```json
{"ok":false,"error":"message must be a JSON object"}
```

## Implemented request types

### `totem.status.get`

Request payload: none.

Result field `status`:

| Field | Type | Meaning |
|---|---|---|
| `version` | string | `totemd` Cargo package version. |
| `uptime_secs` | integer | Seconds since the in-memory `AppState` was created. |
| `config` | object | Effective flattened fallback/policy: `device_name`, `probe`, `verdict_ttl_hours`, `befriend`, and `sync`. |
| `fips.connected` | boolean | Whether the latest FIPS control-socket poll succeeded. |
| `fips.npub` | string or `null` | Local FIPS npub from the latest successful status poll. |
| `fips.mesh_size` | integer | FIPS `estimated_mesh_size`, or `0` before a successful poll. |
| `fips.last_ok_secs_ago` | integer or `null` | Age of the latest successful poll. |
| `fips.last_error` | string or `null` | Latest polling error; cleared after recovery. |
| `peers` | integer | Current authenticated peer count in `totemd`'s snapshot. |
| `recognized` | integer | Peers whose signed proof passed in their current encounter. |
| `claimed` | boolean | Whether one owner pubkey has been persisted. |
| `events` | object | Count of emitted pushes, keyed by event type. |

Example request without the CLI:

```bash
curl --silent http://127.0.0.1:8081/bus \
  --data '{"type":"totem.status.get","id":"health-1"}'
```

### `totem.config.get`

Request payload: none. The result's `config` object contains the effective
flattened fields `device_name`, `probe`, `verdict_ttl_hours`, `befriend`, and `sync`.
This is the same object embedded in `totem.status.get`.

### `totem.peers.get`

Request payload: none.

The result's `peers` array is sorted by first observation and then npub.
Each entry contains:

| Field | Type | Meaning |
|---|---|---|
| `npub` | string | Authenticated FIPS identity. |
| `ipv6_addr` | string | FIPS-derived mesh IPv6 address reported by `show_peers`. |
| `transport_type` | string | Direct peer transport reported by FIPS. |
| `first_seen` | integer | Unix seconds when this `totemd` process first observed the peer. |
| `last_seen` | integer | Unix seconds assigned during the latest snapshot. |
| `probe_verdict` | string or `null` | Cached `candidate`, `not_totem`, or `unreachable` NIP-11 grade. |
| `nip11_name` | string or `null` | Bounded, control-safe unsigned display hint retained for candidates. |
| `recognized` | boolean | Whether the signed challenge passed for this current encounter. |
| `sync_attempt` | integer or `null` | Current periodic reconciliation attempt, starting at 1 for each encounter. |
| `sync_state` | string or `null` | Running or most recent `succeeded`, `failed`, `timed_out`, or `cancelled` outcome for the current encounter. |
| `sync_duration_ms` | integer or `null` | Elapsed runtime while active, then final duration. |
| `sync_exit_code` | integer or `null` | Child exit code when one exists. |
| `sync_error` | string or `null` | Spawn, wait, timeout, or non-zero-exit diagnostic. |

State is process-local: restarting `totemd` resets timestamps, counters,
probe caches, and recognition. A FIPS departure clears that peer's recognition
even without a daemon restart.

### `totem.events.get`

Request payload: none. The result's `events` array contains at most the latest
256 typed pushes from this daemon process, oldest first. Reading history does
not consume it. The array resets on daemon restart and is an operator aid, not
a reliable-delivery queue for SSE consumers.

### `totem.contacts.add` / `totem.contacts.remove`

The message names are reserved, but the current handler always returns:

```json
{
  "type": "totem.contacts.add.result",
  "ok": false,
  "error": "contacts writer not implemented (kind 3 single writer lands with net code)"
}
```

Any other type returns `ok: false` with `unknown type: <type>`.

## Push events

`totemd` uses a Tokio broadcast channel with capacity `256`. A push increments
its type counter, enters a separate 256-entry process-local history ring, and
is sent to current SSE subscribers. The SSE delivery is still discarded when
there is no subscriber; the bounded history remains available through
`totem.events.get`.

Implemented pushes:

| Type | Payload | Trigger |
|---|---|---|
| `totem.peer.seen` | `npub` | A peer appears in a new FIPS snapshot. The first successful poll emits this for already-connected peers. |
| `totem.peer.gone` | `npub` | A peer from the prior snapshot is absent. |
| `totem.peer.candidate` | `npub` | NIP-11 name and public-key claim match the authenticated FIPS npub. |
| `totem.recognized` | `npub` | A strict kind-27235 signed proof passes for the same current encounter. |
| `totem.sync.started` | `npub`, `encounter`, `attempt`, `direction` | A policy-permitted periodic reconciliation round starts. |
| `totem.sync.done` | started fields plus `outcome`, `duration_ms`, `exit_code`, `error`, `summary`, `missing_remote`, `missing_local` | The round exits, times out, or is cancelled; the readable summary survives if optional numeric parsing fails. |
| `totem.owner.claimed` | none | The first valid signer was persisted as owner. |
| `totem.metadata.changed` | `event_id`, `name` | A new device-signed kind 0 was imported. |
| `totem.config.changed` | `config` | Owner policy overrides were persisted and applied. |

SSE example:

```text
event: totem.peer.seen
data: {"type":"totem.peer.seen","npub":"npub1…"}
```

Broadcast lag is dropped by the SSE adapter. Consumers must treat the stream
as notification only and reconcile by calling `totem.status.get` and
`totem.peers.get` after every connection or reconnection.

The spec additionally reserves `totem.befriended`; this revision does not
emit it.

## FIPS watcher behavior

Each poll opens a fresh Unix-socket connection, sends one newline-delimited
JSON command, and reads one response. `totemd` queries `show_peers` and then
`show_status`; it never shells out to `fipsctl`.

When polling fails, `fips.connected` becomes false and `last_error` is set.
The watcher logs the first failure at warning level, repeats at debug level,
and logs recovery once a later poll succeeds. The last peer snapshot remains
available until a successful poll replaces it.

For each new authenticated peer, the watcher probes NIP-11 over its mesh IPv6
address on port `7777`. A candidate requires an `!Totem` name and `pubkey`
matching the FIPS npub. Candidate metadata is unsigned and never sufficient
for recognition. The daemon then sends one fresh random 128-bit nonce to the
peer's challenge responder on port `8080`; a slow response cannot cross a
disconnect/reconnect because recognition also checks the captured
`first_seen` encounter token. A new recognition starts
`/usr/local/libexec/totem-strfry sync ws://[peer]:7777 --dir=both` when policy
permits. After each round finishes, the supervisor waits five minutes and
repeats while the same peer encounter remains recognized and eligible. Rounds
never overlap for one peer; failures and timeouts retry after the same delay.
Duplicate recognition for the encounter is ignored; departure and daemon
shutdown cancel a running child or a waiting loop. Child output is forwarded
to journald and its `Set reconcile complete` line is retained as the round's
human-readable summary. Totemd optionally parses `Have` as events missing on
the remote and `need` as events missing locally; these are set differences,
not acceptance/storage guarantees. A format change leaves the summary intact
and numeric fields null. The child environment remains cleared so signing-
credential paths are not inherited.

## Public challenge endpoint

`GET /totem/challenge?nonce=<32-hex-characters>` returns a Nostr event with:

- kind `27235` and empty content;
- signer equal to the device's FIPS public key;
- exact nonce, endpoint URL, and `GET` tags;
- `Cache-Control: no-store`.

The responder accepts no wall-clock freshness window because offline devices
cannot rely on RTC/NTP. Replay resistance comes from the one-request random
nonce. Signing is bounded by a global eight-signatures-per-second burst
limit. The prover verifies the canonical event ID, Schnorr signature, FIPS
identity, exact shape, and all request bindings.

## Local development

```bash
cd totemd
cargo test --locked
TOTEMD_KEY_PATH=/path/to/test-fips.key cargo run --locked -- serve
```

In another terminal:

```bash
cd totemd
cargo run --locked -- totemctl status
cargo run --locked -- totemctl history
cargo run --locked -- totemctl events
```

The daemon requires a readable signing key at startup. It can run without a
live FIPS daemon once `TOTEMD_KEY_PATH` is supplied, but its watcher reports a
disconnected control socket until one appears. These commands are local-only
and do not restart any system service.
