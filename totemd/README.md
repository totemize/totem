# totemd

Totem control-plane daemon and net code — [spec/10-control-plane.md](../spec/10-control-plane.md).
One binary, two faces: `totemd serve` (daemon) and `totemctl` (bus client).

## Run (dev)

```bash
cargo run -- serve
# env-overridable until ports are pinned in spec 07:
#   TOTEMD_WEB_ADDR=0.0.0.0:8080   public web port
#   TOTEMD_BUS_ADDR=127.0.0.1:8081 loopback bus (never exposed)
# Logging: RUST_LOG (default info); stdout → journald under systemd.
# Config: /etc/totemd/config.toml (override path with TOTEMD_CONFIG).
```

## Configuration

Operator policy lives in `/etc/totemd/config.toml`; see
[`deploy/totemd.toml`](../deploy/totemd.toml). Missing file uses those
defaults; a malformed file fails startup rather than silently running the
wrong policy. Restart `totemd` after edits. FIPS rendezvous/transport remains
in `/etc/fips/fips.yaml`.

`probe = true` runs the cheap NIP-11 prefilter. Candidates are cached for
the daemon lifetime; negative/unreachable results use
`verdict_ttl_hours`. `policy.befriend` is `auto|ask|never`; sync is an
independent toggle.

## Bus

NIP-5D-shaped JSON (`spec/07-conventions.md`), request/result by `id`,
pushes over SSE at `/bus/events`:

```bash
curl -s 127.0.0.1:8081/bus -d '{"type":"totem.status.get","id":"1"}'
curl -sN 127.0.0.1:8081/bus/events        # live push stream
cargo run -- totemctl status              # same thing, pretty
cargo run -- totemctl config              # effective operator policy
cargo run -- totemctl peers               # peers + cached probe grade
cargo run -- totemctl call totem.peers.get
```

## Test

```bash
cargo test
```

## Status

Skeleton: bus + SSE + totemctl. Landed: fips control-socket watcher;
operator config; cached NIP-11 prefilter (peer candidate/not-totem/
unreachable); live `totem.peers.get`; armv6 + aarch64 musl cross builds.
Next: signed challenge → sync supervisor → kind 3 writer.
