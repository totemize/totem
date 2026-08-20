---
title: Ansible deployment runbook
description: Prepare artifacts, deploy safely, verify health, and reason about convergence
---

<!-- generated-by: gsd-doc-writer -->

# Ansible deployment runbook

The playbook in `deploy/ansible/` provisions and converges the complete Totem
service stack:

```text
base → FIPS → strfry → totemd → Python device manager → verification
```

It supports bare Debian/Raspbian systems and adopts the existing hand-installed
bench layout without replacing device identities or relay databases.

## Safety model

Read these rules before a deployment:

- Inventory name and OS hostname are independent. Ansible targets the address
  in `inventory/hosts.yml` and does not rename the machine.
- The supplied `deploy-metot.sh` wrapper always adds `--limit metot`. Use it
  for a one-device rollout; it cannot target another inventory host.
- The play uses `serial: 1`, so a fleet run completes one host before starting
  the next.
- Service restart handlers are enabled by default. Disable them explicitly
  during a no-restart window.
- The Python device-manager role and its checks are enabled by default.
  Disable them when another workstream owns Python managers or drivers.
- Existing `/etc/fips/fips.yaml`, FIPS identity files, strfry operator policy,
  `/etc/totemd/config.toml`, and `/var/lib/strfry/` are preserved. The role
  still reconciles strfry's mesh bind and NIP-11 name/public key, plus managed
  service environment files.
- Inventory stores only each device's public npub/hex identity. Never put a
  private FIPS key or nsec in inventory, vars, or staged artifacts.
- Staged binaries are architecture-specific. The base role stops early if the
  discovered system architecture does not match `totem_system_arch`.
- `--check` is not a complete safety proof for this play: local builds,
  checksum-based artifact installation, service facts, ports, and live health
  checks need a real run. Use syntax check plus a tightly limited real run.

## Inventory

The repository currently defines:

| Inventory host | Address | System arch | Artifact class | Rust target | strfry loader |
|---|---|---|---|---|---|
| `metot` | `192.168.8.239` | `armv7l` | `armv6l` | `arm-unknown-linux-musleabihf` | `ld-musl-armhf.so.1` |
| `totem` | `192.168.8.136` | `armv6l` | `armv6l` | `arm-unknown-linux-musleabihf` | `ld-musl-armhf.so.1` |
| `motown` | `motown.local` (DHCP) | `aarch64` | `aarch64` | `aarch64-unknown-linux-musl` | `ld-musl-aarch64.so.1` |

Treat `deploy/ansible/inventory/hosts.yml` as authoritative for Ansible. Its
per-host `totem_npub` and `totem_npub_hex` values are public identity claims,
not secrets; verification rejects a relay or challenge response that does not
match them. Motown uses mDNS because its numeric DHCP address is not stable.
Metot's 32-bit Zero 2 W kernel reports `armv7l` but intentionally consumes the
backward-compatible armv6 artifact set; `totem_system_arch` and
`totem_artifact_arch` must therefore remain separate.

All hosts use SSH user `totem`, sudo become, and host-key
`StrictHostKeyChecking=accept-new`.

## Controller prerequisites

The controller needs:

- `ansible-playbook` with the built-in modules used by the roles;
- SSH access to the selected target and sudo credentials when required;
- Cargo/rustup and Zig for local `totemd` builds; Ansible installs the
  inventory-selected musl Rust target when absent;
- Python 3 for deterministic device-manager source packaging;
- a locked FIPS source checkout;
- a prebuilt strfry runtime root for each target architecture;
- enough local space for staged archives and Rust targets.

Run commands from the repository root unless a step says otherwise.

## Preflight

### 1. Inspect the exact target

```bash
cd deploy/ansible
ansible-inventory --host metot
ansible metot --module-name ansible.builtin.ping
```

The second command contacts only the named inventory host. Confirm its
resolved `ansible_host`, architecture variables, and intended maintenance
scope before continuing.

### 2. Validate playbook syntax

```bash
cd deploy/ansible
ansible-playbook playbooks/deploy.yml --syntax-check
```

Syntax checking does not contact devices and does not prove artifacts exist.

### 3. Stage target artifacts

FIPS and strfry are built/staged on the controller so small devices never
compile Rust or C++ during deployment:

```bash
deploy/ansible/scripts/stage-artifacts.sh \
  armv6l \
  ../fips \
  /path/to/armv6-strfry-runtime-root
```

For aarch64:

```bash
deploy/ansible/scripts/stage-artifacts.sh \
  aarch64 \
  ../fips \
  /path/to/aarch64-strfry-runtime-root
```

The output is ignored by Git:

```text
deploy/ansible/artifacts/<architecture>/
├── fips/
│   ├── fips
│   ├── fipsctl
│   └── fipstop
├── strfry-rootfs.tar.gz
└── SHA256SUMS
```

The script runs `cargo build --release --locked` for FIPS. Cross-compiling
FIPS still requires the target linker, C headers, and bindgen sysroot expected
by that checkout; installing the Rust target alone is not a complete aarch64
toolchain. Set
`TOTEM_SKIP_FIPS_BUILD=1` only when all three already-built executables are
known to match the locked source; the script still validates and stages them.

Current provenance recorded by the repository:

- FIPS: `23ec0a7b811a0e986fe2d2cb51fffe8f10f7a57d`;
- strfry router lineage: `5e81e24`, with armv6 build/alignment details in
  `.journey/journal/2026-08-20.md`.

Do not treat the `mesh` subcommand or branch name as proof of NIP-77. A live
2026-08-20 check found motown's installed aarch64 relay returned neither
`negentropy: 1` nor NIP `77`; the artifact must be restaged until the verifier
below passes.

Verify `SHA256SUMS` and the target architecture before any remote run.

## Run one guarded deployment

The wrapper below is hard-limited to inventory host `metot`:

```bash
deploy/ansible/scripts/deploy-metot.sh
```

Key-based SSH needs no password variable. If both SSH and sudo require a
password, read it without echoing and export it only for the command's shell:

```bash
read -rs TOTEM_SSH_PASSWORD
export TOTEM_SSH_PASSWORD
deploy/ansible/scripts/deploy-metot.sh
unset TOTEM_SSH_PASSWORD
```

The wrapper passes the value as both `ansible_password` and
`ansible_become_password`. Do not put it in inventory, a committed vars file,
shell history, or a verbose deployment log.

### No-restart maintenance window

To enforce files, packages, units, enabled/running state, and health without
executing notified restart handlers:

```bash
deploy/ansible/scripts/deploy-metot.sh \
  --extra-vars totem_service_restarts_enabled=false
```

This switch suppresses handlers whose action is `state: restarted`. It does
not turn the play into read-only mode: packages and files may still change,
and `state: started` can start a stopped service. If even starting a stopped
unit is prohibited, do not run the play until that maintenance constraint is
lifted.

### Exclude Python managers and drivers

```bash
deploy/ansible/scripts/deploy-metot.sh \
  --extra-vars totem_device_manager_enabled=false
```

This removes Python-specific apt packages, skips the device-manager role,
omits port `8000` and service health checks, and lowers the required migration
count from five to four.

For a no-restart core-only convergence run, combine both guards:

```bash
deploy/ansible/scripts/deploy-metot.sh \
  --extra-vars totem_service_restarts_enabled=false \
  --extra-vars totem_device_manager_enabled=false
```

### Target another host or the fleet

The guarded wrapper must not be repurposed. Run Ansible from its directory and
state the limit explicitly:

```bash
cd deploy/ansible
ansible-playbook playbooks/deploy.yml --limit motown
```

Omitting `--limit` authorizes all hosts in the `totems` group. Because that is
a materially broader action, inspect `ansible-playbook ... --list-hosts` and
obtain the appropriate maintenance authorization first.

## Role behavior

### `base`

- asserts Linux, systemd, and the inventory architecture;
- installs base packages and, unless excluded, Python device packages;
- creates `fips`, `gpio`, `i2c`, and `spi` groups;
- creates/updates user `totem` and appends those groups;
- creates deployment/cache/state directories;
- records migration `0001-bootstrap.complete`.

### `fips`

- requires all three local FIPS binaries and copies changed content;
- creates `/etc/fips` with group access but preserves an existing config;
- seeds a persistent, TUN-enabled config with LAN rendezvous on and no static
  peers only on a bare host;
- installs/enables `fips.service`;
- records migration `0010-fips-layout.complete`.

See [FIPS configuration and implementation](/reference/fips).

### `strfry`

- requires a checksum-addressed runtime archive and expected musl loader;
- creates the `strfry` service account and durable LMDB directory;
- preserves an existing database and operator limits while reconciling the
  IPv6 bind plus the inventory host's `!Totem` name/public identity;
- installs `/usr/local/libexec/totem-strfry`, grants `totem` group-scoped
  config/LMDB access, and preserves group writes with setgid plus
  `UMask=0007`;
- extracts only a runtime checksum not already marked installed;
- installs/enables `strfry.service`;
- records migration `0020-strfry-layout.complete`.

See [strfry configuration and implementation](/reference/strfry).

### `totemd`

- installs the inventory-selected Rust standard-library target on the
  controller when absent;
- builds locally with `cargo build --release --locked --target <target>`;
- manages the IPv6-capable `/etc/totemd/totemd.env` and seeds operator policy
  `/etc/totemd/config.toml` only if absent;
- installs `/usr/local/bin/totemd` and the `totemctl` symlink;
- installs/enables `totemd.service`, passing the root-only FIPS key through
  systemd `LoadCredential=` without changing its source permissions;
- records migration `0030-totemd-layout.complete`.

See [`totemd` CLI and message bus](/reference/totemd).

### `device_manager`

- hashes and deterministically archives the exact current `pyproject.toml`,
  `README.md`, and `src/` bytes, including intentional dirty/untracked source;
- extracts a content-addressed release below
  `/opt/totem/releases/sha256-<digest>`;
- creates a system-site-packages virtual environment and installs the Totem
  package without rebuilding platform dependencies;
- updates `/opt/totem/current`, manages `/etc/totem/totem.env`, and
  installs/enables `totem.service`;
- writes the per-host `TOTEM_EINK_DRIVER` when configured; metot is pinned to
  `waveshare_2in13_v4`;
- records migration `0040-device-manager-layout.complete`.

The role does not edit Raspberry Pi boot firmware or reboot the host. Metot's
`deploy/devices/metot.boot-config.txt` fragment must already be present under
the active boot configuration before `/dev/spidev0.0` and the real display can
be verified.

See [Python device manager](/reference/device-manager).

### `verify`

The final role checks the enabled scope:

1. IPv6 ports `7777` and `8080`, plus loopback bus port `8081`, accept
   connections;
2. port `8000` accepts connections when Python is enabled;
3. core units, plus optional `totem.service`, are enabled and running;
4. `fipsctl show status` reports running state, active TUN, and the exact
   persistent inventory npub;
5. NIP-11 reports negentropy, supported NIP `77`, the exact `!Totem` name, and
   the inventory public key;
6. the root-owned runner opens the relay LMDB successfully as unprivileged
   user `totem`, whose access remains group-scoped;
7. `/totem/challenge` returns a no-store kind-27235 event signed by that same
   FIPS identity, proving the systemd credential and IPv6 web bind;
8. `totemctl status` reports `ok`, a connected FIPS watcher, and valid
   operator policy;
9. Python `/health` returns HTTP `200` when enabled;
10. the expected migration checkpoint count exists.

These are live contract checks. A passing port check alone is not treated as
service health.

## Migration and artifact state

Numbered migration files live in `/var/lib/totem-deploy/migrations/`:

| Checkpoint | Meaning |
|---|---|
| `0001-bootstrap.complete` | Base layout was bootstrapped or adopted. |
| `0010-fips-layout.complete` | FIPS layout/config preservation policy was adopted. |
| `0020-strfry-layout.complete` | strfry runtime/config/database layout was adopted. |
| `0030-totemd-layout.complete` | `totemd` layout was adopted. |
| `0040-device-manager-layout.complete` | Versioned Python layout was adopted. |

Sentinels record completed transitions; they do not suppress desired-state
enforcement. Ansible still checks packages, files, permissions, units, service
state, and health on every run.

Checksum/revision-specific installation markers live in
`/var/lib/totem-deploy/artifacts/`. The strfry marker is keyed by archive
SHA-256; the device-manager marker is keyed by its deployable source digest.

Do not delete sentinels merely to “retry” a deployment. First determine
whether the desired artifact, release, or persistent state is actually
incorrect; removing state can make an intentionally one-time adoption block
run again.

## Convergence expectation

After a successful initial deployment, repeat the same guarded command. With
unchanged source, artifacts, inventory, and host state, Ansible should report
`changed=0`.

An earlier armv6 deployment, before the identity/challenge checks were added,
recorded:

- initial run: `ok=79 changed=32 failed=0`;
- core-only no-restart convergence: `ok=48 changed=0 failed=0`.

Those counts are historical evidence for that exact role scope and revision,
not current expected totals. The identity, policy, and challenge tasks in this
revision legitimately change them.

The first full deployment to physical metot from `totemd` at `54bc749` recorded
`ok=83 changed=9 failed=0`; the immediate full repeat recorded
`ok=79 changed=0 failed=0`.

## Tags and partial runs

Roles expose these tags: `base`, `fips`, `strfry`, `totemd`,
`device_manager`, and `verify`.

Tags are for controlled recovery, not a replacement for dependency reasoning.
For example, `totemd` expects the service account and FIPS group from `base`,
and `verify` assumes its selected services already exist. Prefer the full
limited play; when using tags, name every prerequisite and finish with
`verify`.

List the selected work without changing a host:

```bash
cd deploy/ansible
ansible-playbook playbooks/deploy.yml --limit metot --list-tags
ansible-playbook playbooks/deploy.yml --limit metot --list-tasks
```

## Troubleshooting

### Target architecture assertion fails

Correct `totem_system_arch` when the reported OS architecture is wrong, or
stage the matching `totem_artifact_arch` artifacts. Metot's explicit
`armv7l`/`armv6l` pairing is intentional compatibility; never reuse that
exception to install an armv6 runtime on aarch64.

### “Missing FIPS artifact” or strfry archive

Run `stage-artifacts.sh` for the target's `totem_artifact_arch`, then verify
the generated `SHA256SUMS`. Artifact directories are local and ignored by Git;
another clone or worktree will not contain them automatically.

### strfry loader validation fails

The runtime root used for staging did not include the loader declared by
inventory. Rebuild/export the matching runtime instead of changing inventory
to a loader that happens to exist.

### NIP-11 request returns no JSON

The verifier supplies `Accept: application/nostr+json`. Reproduce with the
same header. Then confirm strfry binds IPv6 with `bind = "::"`.

### `totemctl status` says FIPS is disconnected

Check `fipsctl show status`, control-socket permissions, `totemd`'s
supplementary `fips` group, and `TOTEMD_FIPS_SOCK`. `totemd` polls the socket
directly. Challenge signing separately receives the same root-owned identity
through systemd's private credential directory; it must never read a loosened
source key.

### Signed challenge verification fails

Confirm `/etc/fips/fips.key` is still `root:root` mode `0600`, then inspect
`systemctl cat totemd` for `LoadCredential=fips.key:/etc/fips/fips.key` and
confirm port `8080` listens on IPv6. A stale `TOTEMD_WEB_ADDR=0.0.0.0:8080`
environment file makes LAN IPv4 appear healthy while mesh challenges fail.

### A no-restart run reports changes

The flag suppresses restart handlers, not configuration changes. Review the
task diff and schedule a later restart if a changed binary, unit, or config
cannot take effect live. Do not assume `changed=0` is required on a first
adoption run.

### FIPS process is active but TUN verification fails

Treat the host as degraded. A known upstream failure can leave the TUN thread
dead after a restart. Respect the maintenance window: diagnose first, and only
restart when explicitly allowed; then repeat the full health verification.

## Local-only validation

These checks do not contact inventory hosts:

```bash
cd deploy/ansible
ansible-playbook playbooks/deploy.yml --syntax-check
bash -n scripts/deploy-metot.sh
bash -n scripts/stage-artifacts.sh
```

The Rust daemon can also be checked locally without touching devices:

```bash
cd totemd
cargo test --locked
```
