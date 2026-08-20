---
title: FIPS configuration and implementation
description: Totem's FIPS layout, seed configuration, control socket, IPv6 adapter, and mesh layers
---

<!-- generated-by: gsd-doc-writer -->

# FIPS configuration and implementation

FIPS is Totem's identity-aware encrypted mesh. It authenticates nodes with
Nostr keypairs, routes across heterogeneous transports, and exposes the mesh
to ordinary applications through an IPv6 TUN interface. Totem consumes FIPS
as a separately built daemon; this repository owns its deployment and the
`totemd` control-socket integration, not the upstream protocol implementation.

The Ansible artifact notes pin the current bench baseline to upstream revision
[`23ec0a7b…`](https://github.com/jmcorgan/fips/tree/23ec0a7b811a0e986fe2d2cb51fffe8f10f7a57d).

## Deployed layout

| Path | Purpose | Ownership/mode |
|---|---|---|
| `/usr/local/bin/fips` | Mesh daemon | root, executable |
| `/usr/local/bin/fipsctl` | Control-socket CLI | root, executable |
| `/usr/local/bin/fipstop` | Read-only status TUI | root, executable |
| `/etc/fips/fips.yaml` | Daemon configuration | `root:fips`, `0640` |
| `/etc/fips/fips.key` | Persistent private identity | `root:root`, `0600` by design |
| `/etc/fips/fips.pub` | Public identity material, when generated | non-secret |
| `/run/fips/control.sock` | Local JSON-lines control protocol | group-accessible to `fips` |
| `fips0` | IPv6 overlay TUN interface | kernel network interface |

`fips.service` runs as root because it creates the TUN interface and reads the
root-only identity. `totemd.service` runs as `totem` with supplementary group
`fips`, which is enough to query the control socket. For challenge signing,
systemd's `LoadCredential=` exposes a private read-only copy to that service;
the source key remains `root:root` mode `0600`.

Do not launch `/usr/local/bin/fips` manually while systemd owns the daemon.
Running it as `totem` should fail to read the identity key, and a second root
process would contend for sockets and the TUN interface.

## Totem's seed configuration

Ansible creates this file only when `/etc/fips/fips.yaml` does not already
exist:

```yaml
node:
  identity:
    persistent: true
  rendezvous:
    lan:
      enabled: true

tun:
  enabled: true
  name: fips0
  mtu: 1280

dns:
  enabled: true
  port: 5354

transports:
  udp:
    bind_addr: "0.0.0.0:2121"
  tcp:
    bind_addr: "0.0.0.0:8443"

peers: []
```

This is the ordinary self-forming bench/home seed. It configures no static
peers, but LAN rendezvous lets nearby FIPS nodes discover and authenticate one
another. Set `totem_fips_lan_rendezvous_enabled=false` for an intentionally
isolated deployment.

### Important configuration fields

| Key | Totem value | Operational meaning |
|---|---|---|
| `node.identity.persistent` | `true` | Load or create `fips.key` beside the selected configuration, retaining the same npub across starts. |
| `node.rendezvous.lan.enabled` | `true` | Discover nearby FIPS nodes on the LAN; authentication still uses FIPS identities. |
| `tun.enabled` | `true` | Create the IPv6 adaptation interface. |
| `tun.name` | `fips0` | Stable interface name used by operations and health checks. |
| `tun.mtu` | `1280` | IPv6 minimum MTU and Totem deployment value. |
| `dns.enabled` | `true` | Start the local `<npub>.fips` AAAA responder. |
| `dns.port` | `5354` | Non-standard local DNS port. The upstream default bind is `::1`. |
| `transports.udp.bind_addr` | `0.0.0.0:2121` | UDP transport listener. |
| `transports.tcp.bind_addr` | `0.0.0.0:8443` | TCP transport listener for networks where UDP is unavailable. |
| `peers` | `[]` | No static bootstrap links. |

The service explicitly passes `/etc/fips/fips.yaml`, so user-level or working
directory configuration files do not override the managed daemon.

### Identity policy

With `persistent: true` and no inline `nsec`, FIPS loads `fips.key` if it
exists; otherwise it generates a keypair and stores it beside the config. The
private file remains mode `0600`. Never place `nsec` material in inventory,
documentation, logs, or a staged artifact.

Ansible deliberately preserves both the existing configuration and identity.
`force: false` on the seed template prevents a normal convergence run from
overwriting an enrolled node's peers, discovery settings, or other operator
choices. The inventory's npub/hex fields are public verification claims; the
private key never enters Ansible inventory or an artifact.

## Architecture

FIPS separates the mesh into protocol layers:

| Layer | Responsibility |
|---|---|
| Transport | Send and receive datagrams over UDP, TCP, raw Ethernet, BLE, Tor, or another medium and report its MTU. |
| FMP (mesh) | Authenticate direct peers with Noise IK, encrypt each link, exchange tree/bloom routing state, and forward transit traffic. |
| FSP (session) | Establish end-to-end Noise XK sessions, protect application payload across all hops, and manage destination coordinates/path MTU. |
| IPv6 adapter | Map npubs to `fd00::/8` addresses, adapt IPv6 packets to FSP port 256, manage identity mappings, enforce MTU, and expose `fips0` plus DNS. |

Routing decisions are local. Nodes combine spanning-tree coordinates and peer
bloom filters, falling back to tree routing while caches converge. The
transport below a link does not affect the application above it.

### Identity derivation

One Nostr secp256k1 public key yields three related identifiers:

1. the npub used by people and application integrations;
2. a 16-byte hash-derived `node_addr` used in routing state;
3. an `fd00::/8` IPv6 ULA derived from that node address.

Intermediate routers forward by derived node address. They decrypt and
re-encrypt the hop-by-hop FMP envelope, but the FSP payload remains encrypted
end to end.

### Two encryption scopes

| Scope | Noise pattern | Peers protected |
|---|---|---|
| Link | IK | Two directly connected FIPS nodes |
| Session | XK | Application endpoints, independent of intermediate hops |

Both layers apply even when endpoints are direct neighbors. This keeps the
session model stable if topology changes.

## IPv6 and `.fips` DNS

The DNS responder computes an AAAA address for `<npub>.fips` and registers the
identity mapping needed to route traffic. On Totem it listens on IPv6 loopback
port `5354`; nothing installs it into the device's system resolver.

Query it explicitly:

```bash
dig @::1 -p 5354 AAAA npub1example.fips
```

Applications embedding the resolver should send a DNS AAAA query directly to
`[::1]:5354`. Installing per-device NetworkManager/dnsmasq plumbing would
create configuration asymmetry and is not part of the deployment.

The returned ULA alone is not enough if FIPS has not learned the destination
identity/coordinates. DNS resolution is part of the adapter's routing setup,
not just name presentation.

## Control socket

The daemon accepts one newline-delimited JSON request per local Unix-socket
connection and returns one newline-delimited JSON response. `fipsctl`,
`fipstop`, and `totemd` are clients of this protocol.

Wire example:

```json
{"command":"show_status"}
```

Successful envelope:

```json
{"status":"ok","data":{}}
```

`totemd` opens the socket directly and uses `show_peers` plus `show_status`; it
never launches `fipsctl` as a subprocess.

### Operator commands

These are read-only and safe for routine inspection:

```bash
fipsctl show status
fipsctl show peers
fipsctl show tree
fipsctl show sessions
fipsctl show transports
fipsctl show routing
fipsctl stats metrics
```

The most useful status fields for Totem are:

- `state: "running"`;
- `tun_state: "active"` and `tun_name: "fips0"`;
- `persistent: true` and the expected npub;
- authenticated peer/link counts;
- `estimated_mesh_size` and forwarding counters.

`fipsctl connect` and `disconnect` mutate live mesh state and should not be
used as health probes. `fipsctl keygen` operates on identity files rather than
the daemon; replacing an enrolled identity changes its npub and overlay IPv6
address.

## Totem integration

`totemd` polls FIPS every two seconds by default:

```text
/run/fips/control.sock
  ├── show_peers  ─► npub, IPv6 address, transport type
  └── show_status ─► local npub, estimated mesh size
```

It converts that data into `totem.status.get`, `totem.peers.get`,
`totem.peer.seen`, and `totem.peer.gone`. Candidate peers are then probed over
NIP-11 and challenged over the mesh. The responder signs with the same FIPS
identity received through systemd credentials. See the
[`totemd` bus reference](/reference/totemd).

FIPS transports relay traffic as ordinary IPv6. It has no Nostr relay logic;
strfry remains a separate process listening on the mesh-capable IPv6 wildcard.

## Deployment behavior

The Ansible FIPS role:

1. validates all three architecture-specific artifacts (`fips`, `fipsctl`,
   and `fipstop`) locally and hashes them;
2. creates `/etc/fips` as `root:fips` mode `0750`;
3. seeds configuration only when absent;
4. copies changed executables and installs the systemd unit;
5. records migration `0010-fips-layout.complete`;
6. enables/starts the service;
7. verifies `state`, active TUN, and persistent identity through `fipsctl`.

Changed binaries, units, or a newly seeded config notify a restart handler.
Set `totem_service_restarts_enabled=false` for a no-restart convergence window;
see the [Ansible runbook](/operations/ansible) for the exact command and its
limits.

## Troubleshooting

### `Permission denied` reading the identity key

Expected when a non-root user starts the daemon binary manually. Use the
systemd service. `fipsctl` needs control-socket access through the `fips`
group, not private-key access.

### `.fips` does not resolve through normal applications

Expected on Totem. Query `[::1]:5354` explicitly or use an integration that
implements the FIPS embedder path.

### Service is active but `fips0` is missing

Treat this as degraded even if systemd still reports the process running.
Confirm with `fipsctl show status` and forwarding counters. A known upstream
issue can leave TUN threads dead shortly after a daemon restart; coordinate a
restart only when the current maintenance policy permits it, then verify the
TUN and counters again.

### Mesh ping works but the relay refuses connections

Check strfry's listener independently. The relay must bind IPv6 (`bind =
"::"`) because the FIPS overlay is IPv6. See the
[strfry reference](/reference/strfry).

## Upstream references

- [FIPS repository](https://github.com/jmcorgan/fips)
- [Architecture](https://github.com/jmcorgan/fips/blob/master/docs/design/fips-architecture.md)
- [Configuration](https://github.com/jmcorgan/fips/blob/master/docs/reference/configuration.md)
- [Control socket](https://github.com/jmcorgan/fips/blob/master/docs/reference/control-socket.md)
- [`fipsctl`](https://github.com/jmcorgan/fips/blob/master/docs/reference/cli-fipsctl.md)
