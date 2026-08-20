# totemd

Totem control-plane daemon and net code — [spec/10-control-plane.md](../spec/10-control-plane.md).
One binary, two faces: `totemd serve` (daemon) and `totemctl` (bus client).

## Run (dev)

```bash
TOTEMD_KEY_PATH=/path/to/test-nsec cargo run -- serve
# Pinned service binds (address remains env-overridable):
#   TOTEMD_WEB_ADDR=[::]:8080       public web + challenge (IPv6 + IPv4)
#   TOTEMD_BUS_ADDR=127.0.0.1:8081 loopback bus (never exposed)
#   TOTEMD_SYNC_INTERVAL_SECS=300     delay between periodic sync rounds
#   TOTEMD_SYNC_TIMEOUT_SECS=300      maximum runtime per sync round
# Logging: RUST_LOG (default info); stdout → journald under systemd.
# Fallback config: /etc/totemd/config.toml (TOTEMD_CONFIG).
# Owner state: /var/lib/totemd/state.toml (TOTEMD_STATE).
```

Production does not copy or loosen the root-only FIPS key: systemd
`LoadCredential=` supplies it privately to `User=totem`. Relay commands use
root-owned `/usr/local/libexec/totem-strfry`; group-scoped config/LMDB access
keeps the daemon unprivileged. `GET /` is server-rendered, while a tiny
same-origin client handles first-signer claim, metadata, and policy mutations.
It polls for late NIP-07 injection and offers a development-only, browser-memory
nsec signer; secrets never cross HTTP or enter persistent browser storage.

## Configuration

Deployment fallback lives in root-owned `/etc/totemd/config.toml`; see
[`deploy/totemd.toml`](../deploy/totemd.toml). Missing file uses defaults and
a malformed file fails startup. Owner and policy overrides are atomically
stored in `/var/lib/totemd/state.toml`; public metadata remains a device-signed
kind-0 event in the local relay. FIPS rendezvous/transport remains in
`/etc/fips/fips.yaml`.

`device.name` is the fallback until a valid own kind 0 exists; the effective
name is mirrored into NIP-11 without restarting strfry. `probe = true` runs
the cheap NIP-11 prefilter. Candidates are cached for
the daemon lifetime; negative/unreachable results use
`verdict_ttl_hours`. Candidate rows retain the bounded unsigned NIP-11 name
as `nip11_name`; npub remains the authenticated identity. `policy.befriend`
is `auto|ask|never`. `policy.sync = true` syncs every recognized Totem;
`false` restricts sync to known friends. Eligible peers reconcile immediately
and every five minutes while the encounter remains connected. Completed rounds
retain strfry's readable `Have … need …` summary; parsed set-difference counts
are optional and never affect the sync outcome.

## Bus

NIP-5D-shaped JSON (`spec/07-conventions.md`), request/result by `id`,
pushes over SSE at `/bus/events`:

```bash
curl -s 127.0.0.1:8081/bus -d '{"type":"totem.status.get","id":"1"}'
curl -sN 127.0.0.1:8081/bus/events        # live push stream
cargo run -- totemctl status              # same thing, pretty
cargo run -- totemctl config              # effective operator policy
cargo run -- totemctl peers               # NIP-11 name hint + probe/recognition state
cargo run -- totemctl history             # latest 256 pushes from this daemon run
cargo run -- totemctl events              # future pushes only
cargo run -- totemctl help
cargo run -- totemctl call totem.peers.get
```

The embedded nsec signer is generated from pinned `nostr-tools`/esbuild
versions; rebuild it only when its source changes:

```bash
totemd/web/build-nsec-signer.sh
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
(responder + prover); periodic supervised bidirectional relay sync with live
peer state; bounded event history; server-rendered owner web app with
nonce-bound NIP-98, durable claim/policy state, device-signed kind-0 profiles,
dynamic NIP-11 naming, and armv6 + aarch64 musl cross builds. Next: kind-3
friendship state/actions.
