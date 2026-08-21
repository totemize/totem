# Napplet Verify

Use this skill before claiming a napplet change is complete.

## Static Checks

```bash
pnpm type-check
pnpm build
pnpm test:conformance
```

Read the command output. Do not report success until all pass. `test:conformance`
is authoritative for protocol conformance; `--ui` (`pnpm test:conformance:ui`) gives
a live, re-running visual report.

## Artifact Checks

`pnpm test:conformance` checks the built `dist/` automatically. If inspecting
`dist/index.html` by hand, confirm:

- `napplet-type` meta is present.
- The build is a single self-contained `index.html` with its JS/CSS inlined
  (`vite-plugin-singlefile`). A NIP-5D napplet loads via `iframe.srcdoc` (opaque
  origin), so external `<script src>`/`<link href>` assets cannot be fetched —
  inline is required, not forbidden. No external asset references should remain.
- Expected config-schema metadata when config is declared.

There is no `napplet-aggregate-hash` meta: a napplet cannot contain a hash that
covers itself; the shell computes the aggregate hash from the served files.

## Protocol Checks

- If the change introduces a new message domain, named interface, or numbered
  wire format, verify `docs/new-nap-proposals.md` was followed.
- Confirm app code does not claim support for unaccepted NAPs.
- Confirm any experimental adapter is clearly app-local and not represented as
  shell conformance.

## Runtime Smoke

In a compatible shell:

1. Load the built or dev-served napplet in an `allow-scripts` iframe.
2. Confirm shell capability display renders.
3. Trigger one user action that uses the touched NAP surface.
4. Confirm errors are visible in the app output instead of hidden in console.
5. Confirm long-lived subscriptions close when the iframe unloads.
