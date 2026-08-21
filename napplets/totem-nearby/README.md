# Totem Nearby

A focused NIP-5D napplet for discovering and operating nearby Totem ContextVM
services. It is a separate artifact from the native `totem-myco` integration:
Myco can carry the built `index.html` as a normal file, while a napplet runtime
provides the shell-mediated ContextVM connection to Totems.

## Build brief

- deployment name / d-tag: `totem-nearby`
- new build, created with `napplet create` and initialized with `napplet init`
- single-purpose job: discover Totem ContextVM servers, list their MCP tools,
  and call a user-selected tool with explicit JSON arguments
- required NAP: `cvm`
- optional NAPs: `storage` remembers one Totem; `theme` repaints the whole UI;
  both degrade gracefully when absent
- target shell assumption: the runtime can discover a Totem ContextVM
  announcement and mediate its MCP-over-Nostr transport
- known integration boundary: Myco transfers the artifact but does not itself
  become the napplet runtime or grant the iframe network authority
- relay escape hatches: none

## Start

```bash
pnpm install
kehto paja --target-url http://127.0.0.1:5173 -- pnpm vite --host 127.0.0.1
```

This starts the target at `http://127.0.0.1:5173/` and the Paja runtime at
`http://127.0.0.1:5197/`.

Build and verify the production artifact:

```bash
pnpm verify
```

`pnpm build` uses `@napplet/vite-plugin` to inject napplet metadata and, when
`VITE_DEV_PRIVKEY_HEX` is set, write a local `.nip5a-manifest.json` for hash
workflow testing.

## Conformance Testing

Verify the napplet conforms to the NAP protocol before publishing. Two variants,
mirroring `vitest` vs `vitest --ui`:

```bash
pnpm test:conformance      # headless: build + check; non-zero exit on failure (CI)
pnpm test:conformance:ui   # live web runtime; re-runs on every source change
```

It loads the build into a real `sandbox="allow-scripts"` iframe, drives the
protocol with a reference shell, and fails on a malformed envelope, a manifest
problem, a boot failure, or a forbidden-global reference (e.g. `window.nostr`).

Exacting requirements for a passing build:

- Build to a **single self-contained `index.html`** (`vite-plugin-singlefile` in
  `vite.config.ts`). NIP-5D loads a napplet via `iframe.srcdoc` with
  `sandbox="allow-scripts"` and no `allow-same-origin` (an opaque origin) — there
  is no served origin from which to fetch an external `<script src>`, so the JS
  must be inlined into the one file. External-asset builds do not boot.
- Let the runtime inject `window.napplet` before app code runs. Do not add an
  app-owned shim bootstrap or shell-ready handshake.
- Emit only well-formed envelopes via `@napplet/sdk`; declare every NAP you use in
  `vite.config.ts` `requires`.
- Do not reference `window.nostr` or use direct `fetch`/`WebSocket`/`localStorage`.

The napplet does **not** carry an aggregate hash: a file cannot contain a hash that
covers itself, so the shell computes it from the served files. Conformance does not
check for one.

## Share over Myco

The production artifact is the single file `dist/index.html`. It is well below
Myco's 64 MiB file limit and can be sent like any other HTML file:

```bash
totem-myco send <paired-npub> dist/index.html text/html
```

Receiving it over Myco does not bypass the napplet sandbox; open it in a
NIP-5D runtime that exposes the required `cvm` domain.

## Boundaries

- No direct `fetch`, WebSocket, relay pool, private key, or browser storage.
- ContextVM discovery and MCP tool calls use `@napplet/sdk`'s `cvm` wrapper.
- Remembered selection uses optional shell-scoped `storage`.
- Theme handling uses optional `themeGet` / `themeOnChanged` and includes a
  complete fallback palette.
- Default app-chrome text selection disabled in `src/styles.css`, with
  opt-in controls for copyable or editable regions.
- Context documents for NIP-5D, shell boundaries, package surfaces, and authoring
  patterns.
- Guidance for handling missing NAP interfaces or numbered wire formats without
  submitting unnecessary protocol PRs.
- Local Codex skills for napplet authoring and verification.

## Authoring Context

Read these before changing protocol-facing behavior:

- `docs/nip-5d.md`
- `docs/boundaries.md`
- `docs/design-patterns.md`
- `docs/package-surfaces.md`
- `docs/new-nap-proposals.md`
- `docs/authoring-checklist.md`

The pinned NIP-5D source is referenced from `docs/nip-5d.md`; this template does
not treat its local notes as normative protocol text.

## Text Selection

The starter disables accidental text selection by default. To change the whole
napplet, set `--napplet-text-selection: text` in `src/styles.css`. To opt in one
region, add `data-napplet-select="text"` or `data-napplet-select="all"`.

## Package Scripts

```bash
pnpm dev          # local Vite dev server
pnpm type-check   # TypeScript strict-mode check
pnpm build        # Vite production build
pnpm preview      # preview dist/
pnpm verify       # type-check + build
pnpm test:conformance     # headless NAP conformance (build + check, CI exit code)
pnpm test:conformance:ui  # live conformance web runtime, re-runs on change
```
