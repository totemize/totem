---
title: totemd CLI and message bus
description: Daemon modes, totemctl commands, bus envelopes, event streams, and FIPS polling
---

<!-- generated-by: gsd-doc-writer -->

# `totemd` CLI and message bus

`totemd` is one Rust binary with two faces:

- `totemd serve` starts the control-plane daemon.
- `totemctl …` runs a synchronous client of the daemon's loopback HTTP/SSE
  bus. Deployment creates `totemctl` as a symlink to the same binary.

The implementation is intentionally small in this revision: it watches FIPS,
maintains peer and health state, exposes status/peer requests, and publishes
peer arrival/departure events. It does not yet implement recognition,
contact-list writes, relay sync supervision, or the owner application.

## Daemon command

```text
totemd serve
```

Starting `totemd` without a mode, or with a mode other than `serve` or
`totemctl`, exits with status `2` and prints usage.

### Environment

| Variable | Default | Effect |
|---|---|---|
| `TOTEMD_WEB_ADDR` | `0.0.0.0:8080` | Public HTTP listener. Only `/` exists currently. |
| `TOTEMD_BUS_ADDR` | `127.0.0.1:8081` | Bus listener used by both daemon and `totemctl`. Keep it loopback-only. |
| `TOTEMD_FIPS_SOCK` | `/run/fips/control.sock` | FIPS Unix control-socket path. |
| `TOTEMD_FIPS_POLL_MS` | `2000` | FIPS status/peer polling interval in milliseconds. Invalid values fall back to `2000`. |
| `RUST_LOG` | `info` directive added | tracing filter for daemon logs. |

The deployed defaults live in `/etc/totemd/totemd.env`; the service runs
`/usr/local/bin/totemd serve` as user `totem` with supplementary group
`fips`.

## `totemctl` reference

```text
totemctl status
totemctl peers
totemctl events
totemctl call <type> [json-object]
```

| Command | Bus operation | Output |
|---|---|---|
| `status` | `totem.status.get` | Pretty-printed result object with daemon, FIPS, peer, and push-counter state. |
| `peers` | `totem.peers.get` | Pretty-printed result object containing the current peer array. |
| `events` | `GET /bus/events` | Long-running SSE stream; prints non-empty `event:` and `data:` lines and suppresses keep-alive comments. |
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
| `fips.connected` | boolean | Whether the latest FIPS control-socket poll succeeded. |
| `fips.npub` | string or `null` | Local FIPS npub from the latest successful status poll. |
| `fips.mesh_size` | integer | FIPS `estimated_mesh_size`, or `0` before a successful poll. |
| `fips.last_ok_secs_ago` | integer or `null` | Age of the latest successful poll. |
| `fips.last_error` | string or `null` | Latest polling error; cleared after recovery. |
| `peers` | integer | Current authenticated peer count in `totemd`'s snapshot. |
| `events` | object | Count of emitted pushes, keyed by event type. |

Example request without the CLI:

```bash
curl --silent http://127.0.0.1:8081/bus \
  --data '{"type":"totem.status.get","id":"health-1"}'
```

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

State is process-local: restarting `totemd` resets timestamps and counters.

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
its type counter and is sent to current SSE subscribers. With no subscriber,
the message is discarded after its counter is updated.

Implemented pushes:

| Type | Payload | Trigger |
|---|---|---|
| `totem.peer.seen` | `npub` | A peer appears in a new FIPS snapshot. The first successful poll emits this for already-connected peers. |
| `totem.peer.gone` | `npub` | A peer from the prior snapshot is absent. |

SSE example:

```text
event: totem.peer.seen
data: {"type":"totem.peer.seen","npub":"npub1…"}
```

Broadcast lag is dropped by the SSE adapter. Consumers must treat the stream
as notification only and reconcile by calling `totem.status.get` and
`totem.peers.get` after every connection or reconnection.

The spec reserves additional push names such as `totem.recognized`,
`totem.befriended`, and `totem.sync.*`; this revision does not emit them.

## FIPS watcher behavior

Each poll opens a fresh Unix-socket connection, sends one newline-delimited
JSON command, and reads one response. `totemd` queries `show_peers` and then
`show_status`; it never shells out to `fipsctl`.

When polling fails, `fips.connected` becomes false and `last_error` is set.
The watcher logs the first failure at warning level, repeats at debug level,
and logs recovery once a later poll succeeds. The last peer snapshot remains
available until a successful poll replaces it.

## Local development

```bash
cd totemd
cargo test --locked
cargo run --locked -- serve
```

In another terminal:

```bash
cd totemd
cargo run --locked -- totemctl status
cargo run --locked -- totemctl events
```

The daemon can start without FIPS, but its watcher will report a disconnected
control socket until one appears. These commands are local-only and do not
restart any system service.
