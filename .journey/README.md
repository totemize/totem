# Totem Journey

This directory documents the project's build journey: a dated journal of
what we did, what we found, and what we decided — the context that
doesn't belong in specs (normative) or AGENTS.md (agent instructions),
but is worth keeping.

## The project

Totem is an open-source personal hardware device platform: small carried
devices (Raspberry Pi-based) that each run a Nostr relay, discover each
other, and sync notes when in range — an organic, sneakernet-style
network. See `../spec/` for the normative story, `../AGENTS.md` for the
working environment.

## Journal conventions

- One Markdown file per day: `journal/YYYY-MM-DD.md` (e.g.
  `journal/2026-08-19.md`).
- Written at end of day or as sessions conclude; append to today's file,
  don't rewrite history.
- Content per entry: what was done, findings (measurements, bugs,
  gotchas), decisions and their rationale, and loose ends / next steps.
- Link related commits and files where relevant.
- Findings that become durable rules graduate into AGENTS.md (gotchas)
  or the specs; the journal keeps the story of how we got there.

## Journal index

| Date | Summary |
|------|---------|
| [2026-08-19](journal/2026-08-19.md) | FIPS bring-up triage on totem; metot onboarding; mesh detection checks (ping, DNS, NIP-11 both directions); LAN-vs-mesh benchmark; nak armv6 build + cross-relay NIP-77 sync (host & device-side); nostr-ops benchmark: publish + negentropy via nak vs `strfry sync` (14×/80×/11× — daemon will orchestrate strfry sync); spec: radio modes + `!Totem` AP conventions; AGENTS.md created |
