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
```

## Bus

NIP-5D-shaped JSON (`spec/07-conventions.md`), request/result by `id`,
pushes over SSE at `/bus/events`:

```bash
curl -s 127.0.0.1:8081/bus -d '{"type":"totem.status.get","id":"1"}'
curl -sN 127.0.0.1:8081/bus/events        # live push stream
cargo run -- totemctl status              # same thing, pretty
cargo run -- totemctl call totem.peers.get
```

## Test

```bash
cargo test
```

## Status

Skeleton: bus + SSE + totemctl. Landed next: fips control-socket watch
(net-code loop), challenge endpoint, kind 3 contacts writer, `strfry sync`
supervisor, owner web app.
