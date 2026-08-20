# totemd

Totem control-plane daemon and net code — [spec/10-control-plane.md](../spec/10-control-plane.md).
One binary, two faces: `totemd serve` (daemon) and `totemctl` (bus client).

## Run (dev)

```bash
TOTEMD_KEY_PATH=/path/to/test-nsec cargo run -- serve
# Pinned service binds (address remains env-overridable):
#   TOTEMD_WEB_ADDR=[::]:8080       public web + challenge (IPv6 + IPv4)
#   TOTEMD_BUS_ADDR=127.0.0.1:8081 loopback bus (never exposed)
#   TOTEMD_SYNC_TIMEOUT_SECS=300      maximum runtime per encounter sync
# Logging: RUST_LOG (default info); stdout → journald under systemd.
# Config: /etc/totemd/config.toml (override path with TOTEMD_CONFIG).
```

Production does not copy or loosen the root-only FIPS key: systemd
`LoadCredential=` supplies it privately to `User=totem`. Relay commands use
root-owned `/usr/local/libexec/totem-strfry`; group-scoped config/LMDB access
keeps the daemon unprivileged.

## Configuration

Operator policy lives in `/etc/totemd/config.toml`; see
[`deploy/totemd.toml`](../deploy/totemd.toml). Missing file uses those
defaults; a malformed file fails startup rather than silently running the
wrong policy. Restart `totemd` after edits. FIPS rendezvous/transport remains
in `/etc/fips/fips.yaml`.

`probe = true` runs the cheap NIP-11 prefilter. Candidates are cached for
the daemon lifetime; negative/unreachable results use
`verdict_ttl_hours`. Candidate rows retain the bounded unsigned NIP-11 name
as `nip11_name`; npub remains the authenticated identity. `policy.befriend`
is `auto|ask|never`. `policy.sync = true` syncs every recognized Totem;
`false` restricts sync to known friends.

## Bus

NIP-5D-shaped JSON (`spec/07-conventions.md`), request/result by `id`,
pushes over SSE at `/bus/events`:

```bash
curl -s 127.0.0.1:8081/bus -d '{"type":"totem.status.get","id":"1"}'
curl -sN 127.0.0.1:8081/bus/events        # live push stream
cargo run -- totemctl status              # same thing, pretty
cargo run -- totemctl config              # effective operator policy
cargo run -- totemctl peers               # NIP-11 name hint + probe/recognition state
cargo run -- totemctl help
cargo run -- totemctl call totem.peers.get
```

## Test

```bash
cargo test
cargo clippy --all-targets -- -D warnings
cargo build --release --target arm-unknown-linux-musleabihf
cargo build --release --target aarch64-unknown-linux-musl
```

Cross builds need Zig; `.cargo/zig-musl` maps Rust targets to Zig's bundled
musl headers while `rust-lld` links the static binary. No downloaded cross-GCC
or target sysroot is required.

## Status

Skeleton: bus + SSE + totemctl. Landed: fips control-socket watcher;
operator config; cached NIP-11 prefilter; signed per-encounter challenge
(responder + prover); supervised bidirectional relay sync with live peer state;
armv6 + aarch64 musl cross builds. Next: minimal owner web page, then kind 3
friendship actions.
