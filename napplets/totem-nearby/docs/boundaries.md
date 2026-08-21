# Napplet Boundaries

Napplets run in a restrictive iframe and delegate privileged work to the shell.
The template should stay on the napplet side of that line.

## Napplet Owns

- UI state and rendering.
- User gestures inside the iframe.
- Calls into `window.napplet` through `@napplet/sdk`.
- Feature detection with injected domain property presence.
- Subscription cleanup for relay, identity, config, keys, media, notify, and INC
  listeners.
- Graceful fallback when a shell does not implement a requested NAP.

## Shell Owns

- Relay pool access.
- Signing and encryption.
- User identity and signer state.
- Storage persistence and quota.
- External byte fetching through NAP-RESOURCE.
- Settings UI for NAP-CONFIG.

(NAP-CONNECT direct-network grants and NAP-CLASS security-class assignment are
currently deferred on the NAPs track — not part of the active surface.)

## Forbidden In Napplet Code

- Direct signer access or NIP-07 assumptions.
- Direct host DOM access.
- `localStorage` or `sessionStorage` for durable user data.
- Service worker registration.
- Cookie access.
- Unchecked direct network access.
- Shell policy decisions such as ACL, CSP, resource allowlists, or consent
  persistence.

## Allowed Patterns

- `import { relay, storage, identity } from '@napplet/sdk';` for named helpers.
- `if (window.napplet?.resource) { ... }` before using optional domains.
- `storage.setItem()` for durable key-value app state.
- `resource.bytes()` for external read-only bytes.
