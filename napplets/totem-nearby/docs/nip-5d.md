# NIP-5D Reference

This repository does not contain normative protocol text.

Authoritative pinned source:

`https://raw.githubusercontent.com/dskvr/nips/6ca56324a3764a17141e681225f0aaa0ad45a5b6/5D.md`

Pinned source commit:

`6ca56324a3764a17141e681225f0aaa0ad45a5b6`

Related upstream discussion:

`https://github.com/nostr-protocol/nips/pull/2303`

## What To Use This For

- Confirm the JSON envelope shape for napplet-shell postMessage transport.
- Confirm iframe sandbox assumptions.
- Confirm runtime injection and domain-property availability semantics.
- Confirm that shell-owned services, not the napplet, hold privileged access.

## What Not To Do

- Do not copy protocol requirements into app code as hardcoded shell policy.
- Do not treat this template as the spec.
- Do not infer missing shell behavior from browser side effects.

When protocol behavior appears to conflict with a package README, check the
pinned NIP-5D source and then the current `@napplet` package source.
