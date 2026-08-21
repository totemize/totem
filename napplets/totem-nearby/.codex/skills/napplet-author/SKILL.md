# Napplet Author

Use this skill when adding or changing napplet runtime behavior in this
boilerplate.

## Workflow

1. Read `docs/context-map.md`.
2. Read `docs/boundaries.md` and `docs/design-patterns.md`.
3. Identify the NAP surface involved:
   - relay, identity, storage, inc, keys, media, notify, config, resource,
     connect, or class.
4. If no existing NAP fits, read `docs/new-nap-proposals.md`. Do not invent a
   NAP name, number, or wire domain in app code.
5. Implement using `@napplet/sdk` first. Use `@napplet/nap/<domain>/sdk` only
   when a granular import is materially clearer.
6. Keep shell policy and privileged work out of the napplet.
7. Update `config.schema.json` and `vite.config.ts` when settings, required
   capabilities, or connect origins change.
8. Run `pnpm type-check`, `pnpm build`, and `pnpm test:conformance`.

## Guardrails

- Do not introduce framework dependencies unless the task explicitly requires
  them.
- Do not add direct browser storage for durable data.
- Do not add direct network access (`fetch`/`WebSocket`/`EventSource`).
  NAP-CONNECT, the direct-network grant model, is currently deferred on the NAPs
  track; use `resource.bytes()` for read-only external bytes instead.
- Do not submit or depend on a new wire format unless the NAP proposal guardrails
  are satisfied.
- Close subscriptions during teardown.
