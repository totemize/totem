# AGENTS.md

## Project Overview

Totem is an open-source personal hardware device platform: a small carried
device (Raspberry Pi-based) that runs its own Nostr relay. Totems discover
each other and sync notes when in range — an organic, sneakernet-style
network. Spec lives in `spec/` (numbered docs; `01-overview.md` is the entry
point). Code lives in `totem/` (Go daemon, Python helpers, frontend,
screen-pipe/generator). `references/` holds third-party projects we build
against or borrow from — notably `references/fips/` (the FIPS mesh daemon
that provides the `fips0` overlay network our devices run on) and
`references/strfry/`. These are reference checkouts: read them, don't
refactor them.

## The Device ("totem", the test unit)

- Raspberry Pi (armv6l, Raspbian 13) at `192.168.8.136`.
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

(`~/.ssh/config` has `Host *.fips` → `User totem`, so no user prefix needed.)

- No password needed. If auth fails, the fallback password is `totem`.
- `fipsctl` works as the `totem` user (member of the `fips` group, control
  socket at `/run/fips/control.sock`). Use `sudo` only for root-only things
  (`systemctl restart fips`, reading `/etc/fips/fips.key`, `sudo fipsctl`).

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
