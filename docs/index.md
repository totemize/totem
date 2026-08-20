---
layout: home

hero:
  name: Totem
  text: Device platform documentation
  tagline: Operate the stack, understand its boundaries, and build against its local interfaces.
  actions:
    - theme: brand
      text: System architecture
      link: /architecture/system-overview
    - theme: alt
      text: Ansible runbook
      link: /operations/ansible

features:
  - title: Reproducible deployment
    details: Stage architecture-specific artifacts, deploy one role-driven stack, and verify its runtime contracts.
    link: /operations/ansible
  - title: Local control planes
    details: Use the Rust totemd bus or the Python hardware API without confusing their separate responsibilities.
    link: /reference/totemd
  - title: Mesh and relay internals
    details: See how FIPS supplies identity-aware IPv6 reachability and how strfry stores and reconciles Nostr events.
    link: /reference/fips
---

<!-- generated-by: gsd-doc-writer -->

## What is documented

Totem is a Raspberry Pi-oriented, Nostr-native device platform. Each device
combines a FIPS mesh node, a strfry relay, the Rust `totemd` control plane,
and a Python hardware service. These pages document the code and deployment
that exist in this repository; the numbered files in `spec/` remain the
normative product design.

| If you need to… | Start here |
|---|---|
| Understand processes, ports, trust boundaries, and data flow | [System architecture](/architecture/system-overview) |
| Provision or converge a device | [Ansible runbook](/operations/ansible) |
| Inspect `totemd`, use `totemctl`, or integrate with the local bus | [`totemd` CLI and bus](/reference/totemd) |
| Run or call the hardware API and understand driver selection | [Python device manager](/reference/device-manager) |
| Configure the encrypted overlay and its local control socket | [FIPS reference](/reference/fips) |
| Configure the relay, LMDB storage, NIP-11, and NIP-77 | [strfry reference](/reference/strfry) |
| Wire an E-Ink panel | [E-Ink displays](/hardware/display) |

## Render these docs

Install the pinned VitePress dependency once:

```bash
npm install
```

Then run one command from the repository root:

```bash
npm run docs:dev      # live development server
npm run docs:build    # production build
npm run docs:preview  # serve the production build locally
```

`docs:preview` expects a successful `docs:build` first.
