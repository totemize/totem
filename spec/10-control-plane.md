# 10 — Control Plane (totemd)

Status: Draft

## Role

**totemd** is the totem's control-plane daemon and net code: one
long-running process that implements the pairing loop (`03-network.md`),
serves the web app and its APIs (`06-interaction.md`), and exposes the
message bus the rest of the kernel consumes (`07-conventions.md`). It is
the **single writer** for the device's kind 3 contact list
(`02-identity.md`).

It deliberately does **not** touch relay data traffic: the relay is a
stock server on its own port and nothing is proxied (flatness,
`06-interaction.md`). Recognition data (NIP-11 marker, challenge endpoint)
splits across the two servers; both ports are pinned in `07-conventions.md`.

## Process model

- One Rust binary, two faces: `totemd serve` (the daemon, a systemd unit)
  and `totemctl` (a client of the bus — the same binary in client mode; it
  introduces no separate API).
- Runs as the unprivileged `totem` user. systemd `LoadCredential=` reads the
  FIPS identity key (`/etc/fips/fips.key`, root:root 0600 by design) and
  exposes only a private read-only service credential; source permissions
  are never loosened. The key stays in zeroizing memory and signs challenge
  responses with the device identity (`02-identity.md`). A root-owned runner
  invokes strfry through its bundled musl loader; `totem` belongs to the
  `strfry` group and LMDB stays group-writable, so sync needs no root process.
- Web assets are embedded in the binary; deployment is one binary plus one
  systemd unit.

## Components

| Component | What it does |
|-----------|--------------|
| **Net-code loop** | Watches the fips control socket (`/run/fips/control.sock`, JSON-lines — a direct client, never a `fipsctl` shell-out) for authenticated peers; resolves `.fips` via the documented embedder path (UDP `[::1]:5354`); probes NIP-11; runs the challenge as prover; emits verdicts (`02-identity.md`) |
| **Challenge responder** | `GET /totem/challenge` on the web port; signs kind 27235 with the device key; strict nonce/URL/method binding and a small-burst global signature limit |
| **Contacts writer** | Serialized read-modify-sign-write of kind 3 — the only writer; mutations from pairing, from the owner web app, and from `totemctl` all route through here |
| **Sync supervisor** | Spawns and supervises `strfry sync ws://[peer]:PORT --dir both` per successful verdict; negentropy's design makes interrupted syncs resumable on the next encounter |
| **Web server** | Two binds: the public web port (guest page + relay URL, owner app behind NIP-98, challenge endpoint) and a **loopback-only bind** for the bus |
| **Device manager client** | A client of the local device-manager API (`src/totem/api` — display, NFC, storage, network) for hardware actuation (e.g. show sync state); device events are surfaced on the bus |
| **Encounter log** | Append-only JSONL of verdicts and syncs — the substrate for future encounter records (`09-open-questions.md`) and the source of stats |

## Configuration and engagement policy

Operator policy is read at startup from `/etc/totemd/config.toml`. A missing
file uses the defaults below; a present but malformed file is a startup error (silently
running the wrong social policy is worse than no daemon). FIPS rendezvous and
transport remain in `/etc/fips/fips.yaml`; totemd config controls only what
happens after FIPS reports an authenticated peer.

| Key | Default | Meaning |
|-----|---------|---------|
| `net.probe` | `true` | Run the read-only NIP-11 prefilter on peers |
| `net.verdict_ttl_hours` | `24` | Minimum delay before re-probing a non-totem or unreachable peer |
| `policy.befriend` | `"ask"` | `auto`, `ask`, or `never` publish the peer in kind 3 |
| `policy.sync` | `true` | Opportunistically sync with recognized totems |

The engagement ladder is: FIPS peer seen → NIP-11 candidate → signed
challenge → recognized totem. **Sync and friendship are independent after
recognition.** Sync exchanges public relay data; kind 3 is a published social
claim. `ask` holds a pending request for the owner surface; demo units MAY set
`auto`, while `ask` is the conservative factory default.

The cheap NIP-11 prefilter is graded per npub: candidates stay cached for the
daemon lifetime; non-totem/unreachable results expire after the configured
TTL so a peer that later installs totemd can be discovered. This cache never
replaces authentication: signed challenge verdicts remain per-encounter and
are not cached across encounters (`02-identity.md`). Persisted grades and
escalating backoff are deferred until measurements justify them.

## Owner authentication

NIP-98 (`06-interaction.md`) against an administrator npub allowlist in the
daemon config. This defers the owner-key-vs-device-key question
(`09-open-questions.md`) without blocking v1.

## The bus

Messages use the NIP-5D wire shape; the `totem.*` domain registry lives in
`07-conventions.md` (one home for the vocabulary). Pull via request/result
on the loopback bind, push via SSE (`/bus/events`); pushes are lossy and
consumers reconcile against `totem.status.get` on (re)connect. Diagnostics
stay in journald — peripherals react to typed events, never to logs.

The bus is the v1 seed of the IPC projection (`05-kernel.md`): the NAP
message grammar over plain HTTP, with no napplet machinery (manifests,
ACLs, sessions) — that arrives with happlets and is expected to build on
the same vocabulary.

## Deliberately not in v1

- No relay proxying and no relay fork — the marker rides standard NIP-11
  fields (`07-conventions.md`).
- No happlet runtime, ACL/capability machinery, or custom socket protocol.
- No TLS (`07-conventions.md`), no captive portal, no BLE (fips owns
  transports).
- systemd is the process supervisor; totemd supervises only its own
  children (`strfry sync`).
