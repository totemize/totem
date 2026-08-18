# Totem Specification

Status: **Draft — in design**

This is the specification for Totem, an open-source sneakernet device platform.
It is a set of focused documents, iterated as we design and build.

## Documents

| Doc | Title | Status |
|-----|-------|--------|
| [01-overview.md](01-overview.md) | Introduction, lore, first principles, system overview, terminology | Draft |
| [02-identity.md](02-identity.md) | Unified identity, totem recognition, inter-totem relations | Draft |
| [03-network.md](03-network.md) | Net code: FIPS, transports, discovery, pairing, sync lifecycle | Draft |
| [04-relay.md](04-relay.md) | Relay requirements, policy layer, reference implementation | Draft |
| [05-kernel.md](05-kernel.md) | Kernel parts, message bus, IPC projection, happlets | Draft |
| [06-interaction.md](06-interaction.md) | On-ramps, convergence point, user roles, guest experience | Draft |
| [07-conventions.md](07-conventions.md) | Normative registry: ports, addresses, marker, sync behavior | Draft |
| [08-stories.md](08-stories.md) | User stories and the demo milestone (acceptance test) | Draft |
| [09-open-questions.md](09-open-questions.md) | Non-goals, future directions, open questions | Draft |

Reading order for newcomers: 01 → 06 → 02 → 03 → 04 → 05, then 07 as the
compliance checklist. 08 validates the whole; 09 records what is deliberately
not decided.

## Rules

1. **One home per fact.** Every normative statement (MUST/SHOULD) lives in
   exactly one document. Conventions live in `07-conventions.md`; everything
   else links to it. Duplication is how split specs drift.
2. **Numbers are allocation order, forever.** Filenames are never renumbered;
   a doc may be superseded but keeps its slot (same discipline as NIPs).
   Cross-reference as `03-network.md §pairing`.
3. **The README is the status board.** Docs move Draft → Stable individually as
   we green-light them, so we can iterate on one area without reopening others.

## Language

The key words MUST, MUST NOT, SHOULD, and MAY are to be interpreted as in
RFC 2119.

## References

- `references/fips` — FIPS (Free Internetworking Peering System): self-organizing
  encrypted mesh over Nostr identities, transport-agnostic (WiFi, Bluetooth,
  Ethernet, serial); usable as a local mesh or an overlay on the internet.
- `references/naps` — NAP registry and governance: capability contracts between
  napplets and runtimes, and the projections concept.
- `references/web` — Kehto: web runtime for NIP-5D napplets (shell, runtime,
  ACL, services, firewall packages).
- `references/negentropy.md` — NIP-77: negentropy-based set reconciliation for
  efficient event syncing, client-relay and relay-relay.
- `references/strfry` — strfry: self-contained nostr relay (LMDB), NIP-77 sync,
  plugin interface for policy; our reference relay implementation.

External: NIP-01, NIP-02, NIP-11, NIP-77 as cited per document.
