# Authoring Checklist

Use this checklist before shipping meaningful changes to a napplet.

## App Boundary

- [ ] The app relies on runtime-injected `window.napplet`; it does not import
  `@napplet/shim`.
- [ ] Protocol calls use `@napplet/sdk` or explicit `@napplet/nap/<domain>/sdk`
  helpers.
- [ ] No app code reads or writes signer keys.
- [ ] No app code reads shell DOM, parent cookies, service workers, or host
  storage.
- [ ] Durable app state goes through `storage`.

## Network And Resources

- [ ] Read-only external bytes use `resource.bytes()` or
  `resource.bytesAsObjectURL()`.
- [ ] No direct `fetch`/`WebSocket`/`EventSource` — NAP-CONNECT (direct-network
  grants) is currently deferred on the NAPs track, so there is no active
  direct-network surface.

## Config

- [ ] User-editable settings are represented in `config.schema.json` or the
  `configSchema` object in `vite.config.ts`.
- [ ] Secret fields use `x-napplet-secret: true` and have no `default`.
- [ ] Schema sections use stable `x-napplet-section` names.

## Lifecycle

- [ ] Long-lived subscriptions are closed on teardown.
- [ ] User-triggered operations surface shell errors without crashing the app.
- [ ] The app feature-detects optional NAPs with injected domain property
  presence, e.g. `window.napplet?.resource`.
- [ ] Text that should be copyable opts into selection with
  `data-napplet-select` or a deliberate CSS override.

## Protocol Extensions

- [ ] The feature uses an existing NAP surface when one fits.
- [ ] No new NAP name, number, message domain, or shell conformance language is
  introduced inside this app.
- [ ] If a new NAP seems necessary, `docs/new-nap-proposals.md` has been applied
  and a focused PR to `https://github.com/napplet/naps` is the next step.
- [ ] Experimental app-local adapters are clearly marked as non-protocol and do
  not claim shell support.

## Build

- [ ] `pnpm type-check` passes.
- [ ] `pnpm build` passes.
- [ ] The build is a single self-contained `index.html` (JS/CSS inlined) with no
  external asset references — required for `iframe.srcdoc` loading.
- [ ] Manifest-affecting changes are intentional: config schema, requires list,
  and built artifacts all affect aggregate hash behavior.
