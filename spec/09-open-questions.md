# 09 — Non-Goals, Future Directions, Open Questions

Status: Draft (living document — shrinks as we resolve)

## Non-goals (v1)

- **No Totem-specific relay protocol.** Standard nostr relay + NIP-77;
  nothing more (`04-relay.md`).
- **No privileged peer path.** Flatness is a rule, not a default
  (`06-interaction.md`).
- **No mandatory client software for guests.** The AP is the zero-friction
  path; nothing may require users to run FIPS (`06-interaction.md`).
- **No rich social dynamics yet.** Badges, lineage, games — future event
  kinds on the kind 3 substrate, deliberately not designed now
  (`02-identity.md`).

## Future directions

- **Encounter records** — signed "we met" events (npub, time, maybe counts):
  substrate for badges/lineage games and great lore ("my totem met 12 totems
  today"). Needs a visibility decision first (see privacy below).
- **Richer inter-totem dynamics** on the relations substrate.
- **Happlet ecosystem** — third-party headless applets on the IPC projection
  once `05-kernel.md` matures.

## Open questions

### Kernel / napplets

- Terminology and shape of the headless applet (happlet? happ?) and the IPC
  projection.
- What "shell" means on a headless device; which kernel parts are mandatory
  vs. optional per hardware target.

### Network / radios

- Radio coexistence on constrained hardware: WiFi-as-AP + Bluetooth mesh on
  one radio (Pi Zero W). The natural split is proposed in `03-network.md`;
  confirm feasibility and define multi-radio behavior.
- Is a totem joining another totem's AP as a station a supported v1
  behavior, or only a fallback? It competes for airtime with guest service.

### Relay / sync

- Relay policy: what may guest users write? Should FIPS-authenticated peers
  and anonymous AP guests be treated differently? If yes, **NIP-42 relay
  auth** is the mechanism to bind connection identity at the relay — parked,
  not a v1 promise.
- Moderated content returning via sync: likely answer is that **NIP-09
  deletion (kind 5) events** propagate through sync like ordinary events and
  suppress what they reference. Post-demo validation.
- Scale limits on constrained hardware: event volume, storage budget, sync
  duration during a brief encounter.

### Identity / privacy

- Privacy of relations: are kind 3 contact lists public, or visible only to
  the parties? Encounter records: wanted, and at what visibility? (An open
  contact graph publishes physical movement and social patterns.)
- Key management: does the owner use the totem's npub or a separate admin
  npub? What happens to contacts and mesh identity on key rotation?
- Is any HTTP liveness/capability endpoint needed beyond NIP-11 and signed
  events?

### Guest experience

- Captive portal on AP join? Is the web app read-only for non-owners?

### Conventions (values to pin)

- Port numbers for relay and web app (`07-conventions.md`).
- AP gateway address / ULA choice; captive portal yes/no.
- NIP-11 marker field name (`07-conventions.md`).
