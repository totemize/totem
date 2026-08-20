# Reproducible Totem deploys

This playbook manages FIPS, strfry, `totemd`, and the Python device manager.
It supports both bare Raspbian/Debian devices and the legacy hand-installed
layout already on the bench.

## State model

Numbered checkpoints live in `/var/lib/totem-deploy/migrations/`. They record
one-time layout adoption and let future migrations identify exactly what a
device has crossed. Normal Ansible tasks still enforce binaries, packages,
units, permissions, and service state on every run; a sentinel never hides
configuration drift.

Existing `/etc/fips/fips.yaml`, FIPS identity keys, strfry policy/database
settings, `/etc/totemd/config.toml`, and the strfry database are preserved.
Ansible still reconciles strfry's load-bearing IPv6 bind and NIP-11
name/public key, plus the managed service environment files. A bare host
receives a persistent FIPS configuration with LAN rendezvous enabled and no
static peers. This matches the ordinary self-forming bench/home topology; set
`totem_fips_lan_rendezvous_enabled=false` only for an intentionally isolated
seed.

Inventory pins each bench unit's FIPS npub and hex public key. That public
identity is written into the bare strfry NIP-11 seed and verified against both
the relay document and totemd's signed challenge. Private identity material is
never stored in inventory or artifacts.

Metot's inventory also seeds `TOTEM_EINK_DRIVER=waveshare_2in13_v4` and
`TOTEM_UPS_DRIVER=pisugar2`. The device-manager package set includes
`python3-smbus` for read-only PiSugar2 telemetry. The playbook does not edit
Raspberry Pi boot firmware or reboot a device; apply
`deploy/devices/metot.boot-config.txt` separately before expecting real SPI.

## Prepare artifacts

Builds run on the controller, not the Pi. Stage FIPS from a locked source
checkout and strfry from the matching architecture's runtime root:

```bash
deploy/ansible/scripts/stage-artifacts.sh \
  armv6l ../fips /path/to/armv6-strfry-root
```

The staging script installs the requested Rust standard-library target before
building FIPS. Set `TOTEM_SKIP_FIPS_BUILD=1` only when re-staging already-built
locked outputs (the script still requires all three target binaries).

`totemd` is built automatically with Cargo's locked dependencies and the Zig
musl C wrapper. The Python device manager is archived from the exact current
`README.md`/`pyproject.toml`/`src/` content, including intentional dirty or
untracked source files. A deterministic SHA-256 names the release and its
checkpoint, so two different worktrees cannot alias the same deployment.
Debian's architecture-tested Python packages avoid native compilation on armv6.

## Deploy only metot in this sprint

The inventory contains all three devices, but the guarded wrapper always adds
`--limit metot` (currently `192.168.8.239`):

```bash
read -rs TOTEM_SSH_PASSWORD && export TOTEM_SSH_PASSWORD
deploy/ansible/scripts/deploy-metot.sh
```

Run the same command a second time. A converged deployment must report
`changed=0`, and the verification role checks all four services, FIPS TUN
health, strfry NIP-77 support, an LMDB scan through the unprivileged runner,
`totemd`, the Python health endpoint, and the migration chain. The verification
also requires the `!Totem metot` NIP-11 identity and a kind-27235 challenge
signed by metot's FIPS key.

For an operational no-restart window, keep enforcing files and state while
suppressing all service restart handlers:

```bash
deploy/ansible/scripts/deploy-metot.sh \
  --extra-vars totem_service_restarts_enabled=false
```

When another workstream owns the Python managers/drivers, omit both their role
and their dependencies/health checks without changing the normal deployment
default:

```bash
deploy/ansible/scripts/deploy-metot.sh \
  --extra-vars totem_device_manager_enabled=false
```
