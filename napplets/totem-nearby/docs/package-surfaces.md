# Package Surfaces

## Runtime Packages

If no package exposes the named interface or wire format you need, do not add a
new private message domain in this app. Read `docs/new-nap-proposals.md` and
propose protocol-level work in `https://github.com/napplet/naps` only when the
guardrails are met.

### `@napplet/shim`

Runtime-side injected global installer. Napplet application code does not import
this package.

```ts
import { installNappletGlobal } from '@napplet/shim';
```

The host runtime uses it to install selected `window.napplet.<domain>` objects
before napplet scripts run.

### `@napplet/sdk`

Named helpers for napplet app code.

```ts
import { relay, storage, identity, config, resource } from '@napplet/sdk';
```

Use this for most app code. It wraps `window.napplet` at call time and re-exports
types and constants for common NAPs.

### `@napplet/nap`

Domain-specific subpaths. Use these when you need granular imports.

```ts
import { relaySubscribe } from '@napplet/nap/relay/sdk';
import type { ResourceBytesMessage } from '@napplet/nap/resource/types';
```

Do not import from the `@napplet/nap` root. Import a domain subpath.

## Build Package

### `@napplet/vite-plugin`

Vite plugin for local development metadata and local manifest/hash workflow.

```ts
import { nip5aManifest } from '@napplet/vite-plugin';
```

The plugin injects napplet meta tags, folds config schema into aggregate hash
inputs, and can write a local `.nip5a-manifest.json` when
`VITE_DEV_PRIVKEY_HEX` is set.

Production relay publishing is intentionally outside this boilerplate.
