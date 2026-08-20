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

Existing `/etc/fips/fips.yaml`, FIPS identity keys, `/etc/strfry.conf`, and the
strfry database are preserved. A bare host receives an intentionally isolated
FIPS configuration (`peers: []`, LAN rendezvous disabled). No fleet wiring is
performed by this deployment.

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

`totemd` is built automatically with Cargo's locked dependencies. The Python
device manager is archived from the current git revision and uses Debian's
architecture-tested Python packages, avoiding native compilation on armv6.

## Deploy only metot in this sprint

The inventory contains all three devices, but the guarded wrapper always adds
`--limit metot` (currently `192.168.8.136`):

```bash
read -rs TOTEM_SSH_PASSWORD && export TOTEM_SSH_PASSWORD
deploy/ansible/scripts/deploy-metot.sh
```

Run the same command a second time. A converged deployment must report
`changed=0`, and the verification role checks all four services, FIPS TUN
health, strfry NIP-77 support, `totemd`, the Python health endpoint, and the
migration chain.

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
