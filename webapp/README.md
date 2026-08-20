# webapp

Owner companion app. SvelteKit static site (Svelte 5 + adapter-static);
`npm run build` outputs a self-contained `build/` for totemd to serve.

```bash
npm install
npm run dev     # dev server
npm run check   # svelte-check
npm run build   # static build/
```

## Architecture

State-driven single page (no router). Screens switch on `store.state.screen`.

- `src/lib/types.ts` — domain model (hex pubkeys on the wire, npub display-only)
- `src/lib/api.ts` — the two integration seams:
  - `BusClient` — totemd control plane (status, peers, contacts, settings,
    profile, claim; lossy pushes reconciled via `getStatus`). Mirrors the
    `totem.*` NIP-5D vocabulary (spec 07/10).
  - `RelayClient` — notes, straight to the totem's own local relay.
    Nothing is ever published to external relays.
- `src/lib/mock.ts` — `MockBus` / `MockRelay`. Swap for real clients in
  `src/routes/+page.svelte`; the views never touch transport.
- `src/lib/signer.ts` — owner signing via applesauce (NIP-07 extension,
  NIP-46 bunker). The owner key signs admin/claim events only; kind 0
  profile events are signed by the DEVICE key inside totemd (the app just
  sends the bus request).
- `src/lib/store.svelte.ts` — runes-based store; all mutations are methods.
- `src/lib/screens/`, `src/lib/components/` — pure views.

## Mock state

Claim state and profile persist in localStorage (`mock.*` keys). Reset via
settings → advanced → reset config. On the presence screen, clicking the
pulse (or `window.mockPress()`) simulates the device button press.

## Known stubs

- Guest (unauthenticated) landing view — not built; totemd grew its own
  read-only landing page in the meantime.
- "+ new connection", Search, wipe/rotate — placeholder actions.
- No NIP-98 signing on requests yet (`store.ownerSigner` is kept for it).
- `shortNpub`/`fullNpub` in `format.ts` are display-only fakes, not bech32.
- Ports/URLs follow spec 07 (relay 7777, web 8080); the claim endpoint URL
  in `signer.ts` is a placeholder.
