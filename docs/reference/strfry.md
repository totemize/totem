---
title: strfry configuration and implementation
description: Relay layout, configuration, LMDB architecture, NIP-11, and NIP-77
---

<!-- generated-by: gsd-doc-writer -->

# strfry configuration and implementation

strfry is Totem's Nostr relay. It serves NIP-01 WebSocket clients,
persists events in an embedded LMDB database, publishes a NIP-11 information
document, and provides NIP-77 negentropy reconciliation. Totem does not fork
the relay protocol or proxy relay traffic through `totemd`.

Architecture-specific binaries are staged outside Git. The deployment notes
identify the current bench artifact as router lineage revision `5e81e24`, plus
the armv6 alignment/build work recorded in the journey journal. That pinned
revision is provenance for the staged artifact; it is not present in this
repository and should not be inferred from the current upstream default
branch.

## Deployed layout

| Path | Purpose | Ownership/mode |
|---|---|---|
| `/opt/strfry/bin/strfry` | Relay and maintenance CLI | root-owned runtime artifact |
| `/opt/strfry/lib/` | Architecture-specific musl loader and libraries | root-owned runtime artifact |
| `/opt/strfry/usr/lib/` | Additional runtime libraries | root-owned runtime artifact |
| `/etc/strfry.conf` | Relay configuration | `root:strfry`, `0640` |
| `/var/lib/strfry/` | LMDB environment and relay state | `strfry:strfry`, `0750` directory |
| `/var/cache/totem-deploy/strfry-<sha256>.tar.gz` | Content-addressed deployment cache | root |

`strfry.service` runs as the `strfry` system user with
`WorkingDirectory=/var/lib/strfry`. The service invokes the bundled musl loader
explicitly, so the artifact is self-contained relative to the device's base
distribution:

```text
/opt/strfry/lib/<architecture-loader>
  --library-path /opt/strfry/lib:/opt/strfry/usr/lib
  /opt/strfry/bin/strfry --config=/etc/strfry.conf relay
```

The loader is `ld-musl-armhf.so.1` for the inventory's armv6 devices and
`ld-musl-aarch64.so.1` for aarch64.

## Totem configuration

The important values in the bare-device template are intentionally
conservative for a small device:

```text
db = "/var/lib/strfry/"

dbParams {
    maxreaders = 128
    mapsize = 1073741824
    noReadAhead = false
}

events {
    maxEventSize = 65536
    rejectEventsNewerThanSeconds = 900
    rejectEventsOlderThanSeconds = 94608000
    rejectEphemeralEventsOlderThanSeconds = 60
    ephemeralEventsLifetimeSeconds = 300
    maxNumTags = 2000
    maxTagValSize = 1024
}

relay {
    bind = "::"
    port = 7777
    nofiles = 65536
    realIpHeader = ""

    info {
        name = "!Totem <inventory-hostname>"
        description = "This is a strfry instance."
        pubkey = ""
        contact = ""
        icon = ""
        nips = ""
    }

    maxWebsocketPayloadSize = 131072
    maxReqFilterSize = 200
    autoPingSeconds = 55
    enableTcpKeepalive = false
    queryTimesliceBudgetMicroseconds = 10000
    maxFilterLimit = 500
    maxSubsPerConnection = 20

    writePolicy { plugin = "" }
    compression { enabled = true; slidingWindow = false }
    logging {
        dumpInAll = false
        dumpInEvents = false
        dumpInReqs = false
        dbScanPerf = false
        invalidEvents = true
    }
    numThreads {
        ingester = 1
        reqWorker = 1
        reqMonitor = 1
        negentropy = 1
    }
    negentropy {
        enabled = true
        maxSyncEvents = 1000000
    }
}
```

Ansible writes this only if `/etc/strfry.conf` is absent. Existing relay
identity metadata, operator limits, plugins, and database paths are preserved.

## Configuration guide

### Database

| Key | Totem value | Meaning |
|---|---|---|
| `db` | `/var/lib/strfry/` | LMDB environment directory. Preserve this directory across upgrades. |
| `dbParams.maxreaders` | `128` | Maximum concurrent LMDB readers. |
| `dbParams.mapsize` | `1073741824` | 1 GiB virtual address-map limit, not preallocated disk usage. Capacity planning must account for this ceiling. |
| `dbParams.noReadAhead` | `false` | Keep normal OS read-ahead behavior. |

LMDB permits many readers but only one writer transaction. strfry centralizes
writes in one writer thread and batches work so signature validation and
network I/O do not hold the database write lock.

### Listener and mesh reachability

`relay.bind = "::"` is required for Totem's IPv6-only FIPS overlay. A stock
`0.0.0.0` bind can make LAN tests pass while mesh TCP connections receive
`Connection refused`.

The relay listens on port `7777` for both WebSocket Nostr traffic and NIP-11
HTTP requests. Totem currently uses plain `ws://`/`http://` on-device; the
FIPS path supplies encrypted transport. No reverse proxy is part of the
Ansible deployment.

### NIP-11 identity

The name prefix `!Totem` is the recognition hint specified by Totem. The bare
template leaves `relay.info.pubkey` empty, so it does not yet make a complete
device-identity claim. Populate it with the device public identity according
to the project's recognition policy before depending on NIP-11 recognition.

Retrieve NIP-11 with the required media type:

```bash
curl --silent \
  --header 'Accept: application/nostr+json' \
  http://127.0.0.1:7777/
```

A plain `curl http://127.0.0.1:7777/` may return an empty body; that is not a
valid NIP-11 health check.

The Ansible verification role requires `negentropy` to equal `1` and
`supported_nips` to contain `77`.

### Event limits

The template rejects events more than 15 minutes in the future, more than
three years old, oversized events, excessive tag counts, and oversized tag
values. Ephemeral events older than 60 seconds are rejected and accepted
ephemeral events expire after 300 seconds.

These limits are relay admission/storage policy. They do not alter event
signatures or the Nostr wire protocol.

### Connections and queries

| Key | Totem value | Effect |
|---|---|---|
| `maxWebsocketPayloadSize` | `131072` | Maximum WebSocket frame accepted by the relay. |
| `maxReqFilterSize` | `200` | Maximum filters in one REQ. |
| `maxFilterLimit` | `500` | Maximum records returned per filter. |
| `maxSubsPerConnection` | `20` | Concurrent subscriptions per client. |
| `queryTimesliceBudgetMicroseconds` | `10000` | Initial DB scans yield after a 10 ms CPU budget so shorter queries can run. |
| `autoPingSeconds` | `55` | WebSocket ping interval. |

### Threads

The Totem template chooses one ingester, request worker, request monitor, and
negentropy thread to fit small Raspberry Pi targets. That differs from
upstream's more server-oriented defaults. Increase counts only with measured
CPU, memory, and request-load evidence.

### Compression

Per-message WebSocket compression is enabled. Sliding-window compression is
disabled to reduce per-connection memory. On-disk zstd dictionaries are an
optional maintenance feature and are not configured by Ansible.

### Write policy

`relay.writePolicy.plugin` is empty, so no Totem-specific event-sifter runs.
When configured, a plugin receives one JSON line per candidate event on stdin
and returns an `accept`, `reject`, or `shadowReject` decision. Plugin policy is
in addition to strfry's normal validation; an `accept` cannot bypass invalid
event checks.

## Implementation overview

strfry uses a shared-nothing, inbox-driven thread architecture. Threads
communicate through non-copying queues and LMDB rather than concurrently
mutating common in-memory structures.

| Component | Responsibility |
|---|---|
| WebSocket thread | Multiplex connections and route frames; avoids JSON parsing and database work. |
| Ingester pool | Decode JSON, validate/hash events, verify signatures, and compile filters. |
| Writer | Serialize LMDB writes, deletions, and replaceable-event handling. |
| ReqWorker pool | Scan existing indexed data for the initial phase of each REQ. |
| ReqMonitor pool | Watch LMDB changes and match newly written events against active subscriptions. |
| Negentropy pool | Reconcile sets for NIP-77 `NEG-*` messages, optionally using precomputed trees. |
| Cron | Apply retention policy and expire ephemeral events. |

### Storage model

Indexed event fields use packed representations and LMDB indices clustered by
`created_at`; canonical raw event JSON is stored separately. Query plans are
selected from the constrained Nostr filter vocabulary rather than generated
through SQL.

Initial scans can pause and resume after their time budget. This prevents one
large historical query from monopolizing a request worker while new queries
wait. Live subscriptions then move to ReqMonitor, which observes database
changes—including events written by import, sync, or another process sharing
the LMDB environment.

### NIP-77 negentropy

Negentropy compares ordered sets of event IDs so peers exchange the differences
instead of full databases or full ID lists. A session uses `NEG-OPEN`,
alternating `NEG-MSG` frames, and `NEG-CLOSE`; normal EVENT transfers carry the
missing records after reconciliation.

The local CLI can reconcile in either direction:

```text
strfry sync ws://[peer-fips-ipv6]:7777 --dir down
strfry sync ws://[peer-fips-ipv6]:7777 --dir up
strfry sync ws://[peer-fips-ipv6]:7777 --dir both
```

`totemd` does not invoke these commands yet. The sync supervisor described in
`spec/10-control-plane.md` remains planned.

## Operator checks

### Service and listener

```bash
systemctl status strfry --no-pager
ss -ltnp | grep ':7777'
```

The listener must include IPv6. Check NIP-11 separately with its Accept
header, then use an actual WebSocket/Nostr client for protocol behavior.

### Running maintenance subcommands

The deployed binary relies on its bundled loader and libraries. Copy the
loader and library-path prefix from `systemctl cat strfry`, then replace the
final `relay` subcommand with the desired read-only command. For example, the
shape is:

```text
/opt/strfry/lib/<loader> \
  --library-path /opt/strfry/lib:/opt/strfry/usr/lib \
  /opt/strfry/bin/strfry --config=/etc/strfry.conf scan '{}'
```

Run database-reading commands as `strfry` so ownership and environment match
the service. Commands such as `delete`, `import`, database upgrade, and
compaction mutate durable relay data; schedule and back up those operations
instead of using them as diagnostics.

## Deployment behavior

The Ansible strfry role:

1. hashes the architecture-specific runtime archive on the controller;
2. creates the `strfry` user and durable database directory;
3. seeds an IPv6-capable config only when absent;
4. copies the archive into a checksum-addressed remote cache;
5. extracts only an artifact whose installation sentinel is absent;
6. verifies the architecture-specific musl loader;
7. installs/enables the systemd unit and records migration
   `0020-strfry-layout.complete`;
8. verifies NIP-11 and NIP-77.

The LMDB directory is never replaced by the artifact extraction. Changed
runtime content notifies a restart handler; the no-restart switch in the
[Ansible runbook](/operations/ansible) suppresses that handler during a
maintenance freeze.

## Troubleshooting

### LAN works but FIPS mesh connections fail

Confirm `/etc/strfry.conf` contains `bind = "::"`, then confirm an IPv6
listener exists. FIPS addresses are IPv6 ULAs; an IPv4-only listener cannot
accept them.

### NIP-11 body is empty

Supply `Accept: application/nostr+json`. An empty response to a generic GET is
expected behavior and does not prove the relay is unhealthy.

### NIP-77 verification fails

Check `relay.negentropy.enabled`, the built artifact's supported NIPs, and the
NIP-11 JSON. The Totem verifier expects both the negentropy flag and NIP `77`.

### Artifact starts from a shell but not systemd (or vice versa)

Compare the exact loader and `--library-path` prefix with the unit. Executing
`/opt/strfry/bin/strfry` without its staged musl runtime can fail even though
the binary itself is present.

## Upstream references

- [strfry repository](https://github.com/hoytech/strfry)
- [Architecture and operation](https://github.com/hoytech/strfry#architecture)
- [Negentropy protocol](https://github.com/hoytech/strfry/blob/master/docs/negentropy.md)
- [Event-sifter plugins](https://github.com/hoytech/strfry/blob/master/docs/plugins.md)
