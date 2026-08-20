# Totem web app

The Svelte 5 owner interface served by `totemd` at `/`. It is a client-only,
single-page Vite build; totemd embeds the generated HTML, CSS, and JavaScript
in its Rust binary, so devices need no Node runtime or loose web files.

```bash
npm ci
npm run check
npm run build       # writes ../totemd/web/static/{index.html,app.js,app.css}
npm run dev         # proxies /api and /nsec-signer.js to localhost:8080
```

Commit the generated `totemd/web/static/` files with source changes. CI rebuilds
them and rejects stale output before running the Rust checks.

## Runtime boundaries

- Public state comes from same-origin `GET /api/status`.
- Public `/api/updates` SSE contains invalidations only; it never exposes peer
  identities or the generic bus.
- Claim, profile, and policy mutations retain totemd's nonce/body-bound NIP-98
  authorization.
- Owner mode opens one NIP-98-authenticated `/api/owner/events` stream. Its
  first frame contains current status, peers, and the daemon's bounded history;
  later frames contain the same current state plus each typed push.
- `/bus` and `/bus/events` remain loopback-only on port 8081. The browser never
  connects to them, and `totemctl` remains their client.
- Owner signing uses any late-injected standard NIP-07 provider. nos2x's
  manifest does not expose its provider script to private-LAN HTTP origins, so
  a small fallback speaks its already-running content-script bridge when
  `window.nostr` is absent. The existing development nsec bundle remains a
  lazy, page-memory-only fallback and is cleared on navigation.

The implemented UI intentionally stops at current backend capabilities:
profile, engagement policy, aggregate status, current recognized Totems, and
process-local activity. Notes, kind-3 friendship, durable encounters, hardware
vitals, reset, and relay moderation return only when their real backend slices
exist; the production app contains no mock state.
