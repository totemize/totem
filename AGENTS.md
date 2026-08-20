# AGENTS.md

## Project Overview

Totem is an open-source personal hardware device platform: a small carried
device (Raspberry Pi-based) that runs its own Nostr relay. Totems discover
each other and sync notes when in range — an organic, sneakernet-style
network. Spec lives in `spec/` (numbered docs; `01-overview.md` is the entry
point). Code lives in `src/totem/` (Python hardware runtime: device
managers, drivers, FastAPI/WS API; tests in `tests/`, units in
`deploy/systemd/`). The control-plane daemon **totemd** (Rust) lives at
`totemd/` in this repo (`spec/10-control-plane.md`; monorepo for spec-
atomic iteration and one deploy story — split criteria in journal
2026-08-19). `references/` holds third-party projects we build
against or borrow from — notably `references/fips/` (the FIPS mesh daemon
that provides the `fips0` overlay network our devices run on) and
`references/strfry/`. These are reference checkouts: read them, don't
refactor them.

## Journal (.journey/)

The project keeps a dated journal in `.journey/journal/YYYY-MM-DD.md` —
what was done, findings (measurements, bugs, gotchas), decisions and
rationale. Start new sessions by reading the latest entries; when a
session closes, append to today's file (create it if absent) and add a row
to the index in `.journey/README.md`. Durable rules graduate from the
journal into this file or the specs; the journal keeps the story.

## The Devices

### totem (test unit #1)

- Raspberry Pi (armv6l, Raspbian 13) at `192.168.8.136`.
- FIPS npub: `npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q`
- Runs `fips.service` (FIPS mesh daemon, binary at `/usr/local/bin/fips`,
  config at `/etc/fips/fips.yaml`, identity key `/etc/fips/fips.key` —
  root:root 0600 by design; do not loosen).

### SSH access

Passwordless key auth is already set up; `~/.ssh/config` has an alias:

```bash
ssh totem 'command'     # runs as user totem@192.168.8.136
scp file totem:/tmp/    # file transfer
```

Also reachable over the FIPS mesh itself, by its mesh address
(this device's npub — DNS resolves it via the fips `.fips` responder):

```bash
ssh npub1eu0clm0nsxwavcsj07at3sy7v52tuwgw4qpeqsyxgkeqg7krc7ps77c20q.fips
```

### metot (test unit #2)

- Host `metot` at `192.168.8.239`, same image/user/pass scheme as totem.
- FIPS npub: `npub1j0adney3t3tuvcaz6wv6eahpkhfrl8rwhry58n2u4njuxz0j04lsrudpf6`

```bash
ssh metot               # via LAN
ssh metot.fips          # via FIPS mesh
```

(`~/.ssh/config` has `Host *.fips` → `User totem`, so no user prefix needed.)

- No password needed. If auth fails, the fallback password is `totem`.
- `fipsctl` works as the `totem` user (member of the `fips` group, control
  socket at `/run/fips/control.sock`). Use `sudo` only for root-only things
  (`systemctl restart fips`, reading `/etc/fips/fips.key`, `sudo fipsctl`).

### motown (test unit #3)

- Fresh unit, onboarded 2026-08-20. Debian 13 (trixie), **aarch64** (64-bit —
  unlike totem's armv6l; cross-builds need the aarch64 target).
- Reaches LAN via mDNS: `motown.local` → `192.168.8.196` (address is
  DHCP — mDNS name is the stable handle).
- `~/.ssh/config` alias `motown` (User `totem`); our key is installed,
  passwordless works. Fallback password: `totem`.
- FIPS npub: `npub1rx7epldvux4d306aasw0n6y7wn9je0wa3yw4f8djpsw28g8zqzxsgg2g35`
  (`fips.service` running, same layout as totem: binaries in
  `/usr/local/bin`, config+key in `/etc/fips/`, `totem` in the `fips`
  group; static aarch64 musl build of the same checkout as totem —
  BLE off like the others).

```bash
ssh motown               # via LAN
ssh motown.fips          # via FIPS mesh
```

- Runs the same strfry as totem (`references/strfry` `router` branch — has
  the `mesh` app; aarch64 build, alpine-minirootfs runtime under
  `/opt/strfry`, `bind = "::"` set): relay on port 7777, verified over LAN
  and over the mesh from totem.
- NIP-11 markers per 07 conventions (2026-08-20): `info.name =
  "!Totem motown"`, `info.pubkey` = hex npub `19bd90fd…2008d` (renders,
  verified over mesh — `pubkey` is the load-bearing claim, present since
  strfry's first commit); `info.self` kept as dormant duplicate until a
  strfry upgrade understands it. Footgun: golpe takes the LAST duplicate
  key — set the stock `pubkey = ""` line, don't add a second one.

### totemd (all three bench units)

- Standing install: `/usr/local/bin/totemd`, `totemctl` symlink,
  `totemd.service` enabled; deploy/update with `deploy/flash.sh [devices]`.
- Operator policy: `/etc/totemd/config.toml` (created only when absent —
  flash never clobbers edits); restart totemd after changes.
- Signed challenge build is currently deployed to totem + motown only;
  metot intentionally remains on the pre-challenge build during parallel
  peripheral work (it will appear as `candidate`, not `recognized`).
- Challenge signing key on enabled units: source remains
  `/etc/fips/fips.key` root:root 0600; `totemd.service` passes it to `User=totem` with systemd `LoadCredential=`.
  Do not copy it, print it, or loosen its mode.

```bash
ssh totem 'totemctl status'  # fips health + effective policy + counters
ssh totem 'totemctl peers'   # peers + NIP-11 hint + probe/recognition state
ssh totem 'totemctl config'  # effective engagement policy
```

### Device inspection conventions

```bash
ssh totem 'fipsctl show status'   # state, peers, mesh size, forwarding counters
ssh totem 'fipsctl show peers'    # authenticated peers + link quality
ssh totem 'fipsctl show tree'     # spanning-tree position
ssh totem 'systemctl status fips' # daemon health
```

- Parse `fipsctl` JSON with `python3 -c 'import json,sys; ...'` locally
  after piping out.
- Journal timestamps are local (WEST, UTC+1) but fips log lines are UTC —
  mind the offset when correlating.
- Do not run `/usr/local/bin/fips` manually as non-root: it exits 1 with
  "Permission denied" reading the identity key (by design) and would clash
  with the running daemon anyway.

## Known Issues (as of 2026-08-19)

- TUN threads can die silently shortly after a `systemctl restart fips`:
  state latches `degraded`, `fips0` vanishes, forwarding counters freeze,
  nothing is logged. Fix: restart again. Upstream fix pending in fips.

## Gotchas

Things that cost us debugging time. Check here first when something
"mysteriously" fails.

### `.fips` names don't resolve via the system resolver (by design)

Nothing wires `.fips` into the device resolver, and fips deliberately
  doesn't hijack system DNS (its responder binds `[::1]:5354`). Apps query
  it directly — this is the documented embedder path and what our net code
  should use:

```bash
ssh totem 'python3 -c "...udp query to (\"::1\",5354)..."'   # see below
```

One-liner resolver (any device, any user):

```python
import socket
q=b"\xab\xcd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
for l in "<npub>.fips".split("."): q+=bytes([len(l)])+l.encode()
q+=b"\x00\x00\x1c\x00\x01"
s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM); s.settimeout(3)
s.sendto(q,("::1",5354)); r=s.recvfrom(512)[0]
print(socket.inet_ntop(socket.AF_INET6, r[-16:]))
```

Don't install resolver plumbing per-device (NM dnsmasq plugin etc.) —
tried on totem, reverted 2026-08-19; devices stay symmetric.

### Mesh-facing services must bind IPv6

The mesh is IPv6-only (`fd00::/8`). Stock strfry's `0.0.0.0` and a totemd
web bind of `0.0.0.0:8080` both make mesh SYNs get RST ("Connection
refused") while LAN and pings work. strfry must use `bind = "::"`; totemd
defaults to `[::]:8080` (dual-stack on the device images).

strfry was fixed on totem+metot 2026-08-19, motown 2026-08-20 (config copied
verbatim; `/etc/strfry.conf` line 44). Re-check after any relay reinstall or
service bind override.

### Dev host also runs fips

The workstation runs its own fips node, so `.fips` ssh works from the
host even though devices can't system-resolve `.fips`. Don't take host-
side `.fips` success as evidence of device-side wiring.

### Journal timestamps: local (WEST) vs fips logs: UTC

journalctl prints local time (UTC+1); fips log lines are UTC. Subtract
1h from journal-stamped fips lines when correlating with the log text.

### Running `/usr/local/bin/fips` by hand as `totem` fails — on purpose

`fips.key` is root:root 0600 (by design). A manual run exits 1 with
"Permission denied". Daemon is systemd-managed; use `fipsctl`, never
the binary.

### NIP-11 needs the Accept header

`curl http://host:7777/` returns empty; strfry serves the info doc only
with `-H "Accept: application/nostr+json"`.

### Restarting NetworkManager drops your ssh session

The remote command keeps running — reconnect and verify state instead of
assuming failure.
