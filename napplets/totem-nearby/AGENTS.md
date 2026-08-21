# Napplet Boilerplate Agent Guide

This repository is a starter for one NIP-5D napplet. Keep it small,
framework-light, and centered on the napplet side of the shell boundary.

## Before Editing

1. Read `docs/context-map.md`.
2. Read the boundary document for the surface you are changing:
   - `docs/boundaries.md`
   - `docs/design-patterns.md`
   - `docs/package-surfaces.md`
3. If changing protocol assumptions, verify against the pinned NIP-5D reference
   in `docs/nip-5d.md`.
4. If the change appears to need a new NAP name, message domain, or numbered
   wire format, read `docs/new-nap-proposals.md` before writing code.

## Hard Boundaries

- Do not add shell implementation code to this template.
- Do not access signer keys, relay pools, cookies, service workers, or host DOM
  directly from napplet code.
- Do not use `localStorage` or `sessionStorage` for durable app state. Use
  `@napplet/sdk` storage helpers.
- Do not use direct `fetch`, `WebSocket`, or `EventSource`. NAP-CONNECT (the
  direct-network grant model) is currently deferred on the NAPs track, so there
  is no active direct-network surface. Use `resource.bytes()` for read-only
  external bytes.
- Do not import `@napplet/shim` from napplet code. The runtime injects
  `window.napplet`; app code uses `@napplet/sdk` or direct domain properties.
- Do not invent app-local NAP names, numbers, or JSON envelope domains. Open a
  proposal PR to `napplet/naps` only after the guardrails in
  `docs/new-nap-proposals.md` are satisfied.

## Verification

Run these before claiming completion:

```bash
pnpm type-check
pnpm build
pnpm test:conformance
```

`test:conformance` loads the built napplet in a real `allow-scripts` iframe and
fails on a malformed envelope, a manifest problem, a boot failure, or a
forbidden-global reference. Use `pnpm test:conformance:ui` for the live runtime.

Use `pnpm dev` for shell/manual testing. A passing browser smoke test should
cover iframe load, shell capability display, and at least one user-triggered SDK
operation in the target shell.
