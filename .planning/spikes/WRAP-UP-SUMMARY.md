# Spike Wrap-Up Summary

**Date:** 2026-08-22
**Spikes processed:** 5
**Feature areas:** process topology, driver IPC, dual-host lifecycle
**Skill output:** `./.codex/skills/spike-findings-totem/`

## Processed Spikes

| # | Name | Type | Verdict | Feature Area |
|---|------|------|---------|--------------|
| 001a | Per-binding isolation | comparison | PARTIAL | Process topology |
| 001b | Per-provider isolation | comparison | PARTIAL | Process topology |
| 002a | NIP-5D framed JSON | comparison | PARTIAL | Driver IPC |
| 002b | NIP-5D MessagePack | comparison | PARTIAL | Driver IPC |
| 003 | Dual-host contract and failure parity | standard | VALIDATED | Dual-host lifecycle |

## Key Findings

- Use one isolated process per provider distribution as the provisional
  default. Keep per-binding grouping as an explicit smaller-crash-domain
  override. Lock the default only after Linux PSS and realistic plugin-import
  measurements on armv6l/armv7l and aarch64 hardware.
- Use canonical JSON for the NIP-5D-shaped v1 control envelope and carry binary
  values as bounded, checksummed raw attachments behind a versioned 16-byte
  prefix. Reserve MessagePack as an optional codec; its full display-frame
  saving was only 47 bytes and its fleet installation path is unresolved.
- Require both host adapters to pass the same functional conformance suite,
  but document containment separately. Process mode supports hard termination,
  restart, and lease release after confirmed child death. In-process mode uses
  cooperative cancellation; an uncooperative timeout contaminates the host and
  retains leases until controlled daemon restart.
- Keep the accepted ontology intact during implementation: models are facts,
  capabilities are versioned contracts, drivers are independently installable
  providers, resolution is deterministic, `screen` consumes narrow ports, and
  current managers/APIs remain migration facades.

## Remaining Gates

- Run the topology and carrier harnesses on fleet architecture classes using
  Linux PSS, representative imports, and real display transfers.
- Verify dependency installation/build behavior for every supported artifact
  class before locking runtime budgets.
- Design and verify least-privilege enforcement separately: service identity,
  device-node allowlists, D-Bus policy, systemd sandboxing, and resource
  handoff.
- Turn the architecture, 33 requirements, and these implementation blueprints
  into an executable Phase 1 plan before modifying production Python.
