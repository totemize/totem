# Totem Hardware Runtime

## What This Is

Totem is an open-source personal hardware platform whose Python runtime exposes
display, power, storage, NFC, Wi-Fi, Bluetooth, and future hardware capabilities
to local applications. This work replaces the current type-specific device
manager hierarchy with a capability-oriented runtime and a public driver plugin
contract.

## Core Value

Maintainers can add independently packaged hardware drivers without editing
Totem core or destabilizing existing capabilities.

## Requirements

### Validated

- ✓ Existing Python entry points, HTTP routes, environment variables, and
  systemd unit names are deployed compatibility contracts.
- ✓ PR #22 supplies policy-free Wi-Fi, Wi-Fi Direct, Wi-Fi Aware, Bluetooth,
  BLE, GATT, and L2CAP primitives that the new runtime must retain.

### Active

- [ ] Model physical hardware as discovered facts and data-driven profiles,
  rather than a closed class hierarchy of device types.
- [ ] Support independently installable, versioned third-party driver packages.
- [ ] Run drivers in isolated processes by default with explicit global or
  per-plugin in-process opt-in.
- [ ] Resolve compatibility deterministically from manifests and observed
  evidence, failing closed on ambiguity.
- [ ] Preserve existing callers through compatibility facades throughout the
  migration.

### Out of Scope

- Replacing the Rust `totemd` control plane — this phase restructures the
  Python hardware runtime and its clients.
- Embedding product engagement or synchronization policy in drivers — drivers
  expose hardware capability primitives only.
- Treating runtime process isolation as supply-chain trust — installing a
  third-party distribution remains an administrator trust decision.

## Context

The PR #22 baseline has useful typed radio capabilities and realistic Linux
backends, but driver registries, manager factories, hardware detection, and API
composition remain centralized by device type. The new `screen` application is
a separate deployable client, but its placement alongside `devices`, `managers`,
and `api` made the mixed taxonomy visible.

## Constraints

- **Baseline**: Work branches from PR #22 commit `211f890b222c6108dc63c57e6e18fc64ed8d8d97`.
- **Compatibility**: Keep `totem`, `totem-api`, and `totem-screen` commands,
  deployed service names, legacy Python imports, routes, and environment names.
- **Platforms**: The runtime must remain practical on armv6l, armv7l, and
  aarch64 Raspberry Pi-class devices.
- **Security**: Isolated mode must not import third-party driver code into the
  hardware daemon and must use a non-executable serialization protocol.
- **Architecture**: Core runtime modules may depend on public driver contracts;
  public contracts must never depend on runtime or concrete drivers.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Capabilities, not device subclasses, are the stable abstraction | Physical models and combinations are unbounded; behavior changes more slowly | — Pending |
| Third-party drivers are independent Python distributions | New hardware must not require a Totem core release | — Pending |
| Process-isolated driver execution is the default | A failed plugin should not take down the hardware daemon | — Pending |
| In-process execution remains an explicit option | Trusted or constrained deployments may prioritize latency and memory | — Pending |
| Both hosts implement one transport-neutral contract | Behavior and tests must not fork by execution mode | — Pending |
| Driver messages use a NIP-5D-shaped logical envelope | Reuses Totem's existing `type`/`id`/`.result` vocabulary while allowing the carrier to change | — Pending |

---
*Last updated: 2026-08-22 after hardware ontology exploration*
