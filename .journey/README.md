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
| [2026-08-19](journal/2026-08-19.md) | FIPS bring-up triage on totem; metot onboarding; mesh detection checks (ping, DNS, NIP-11 both directions); LAN-vs-mesh benchmark; nak armv6 build + cross-relay NIP-77 sync (host & device-side); nostr-ops benchmark: publish + negentropy via nak vs `strfry sync` (14×/80×/11× — daemon will orchestrate strfry sync); spec: radio modes + `!Totem` AP conventions; AGENTS.md created; repo reduced to Python hw stack (PR #9); totemd design session — control plane specced (`spec/10`): no relay proxy, marker via NIP-11 `name`/`self`, challenge on web port, NIP-5D bus over loopback HTTP/SSE, totemctl client; versioned E-ink drivers deployed and initial screenless-totem electrical triage recorded (corrected on 2026-08-20) |
| [2026-08-20](journal/2026-08-20.md) | motown onboarding (test unit #3, aarch64): mDNS discovery, ssh alias + passwordless key; fips bring-up — aarch64 musl cross recipe (gnu blocked by libdbus-sys), totem-mirrored deploy, mDNS auto-pair, mesh verified (ping/DNS/ssh); initial strfry aarch64 build/deploy, later found wire-incompatible and upgraded to protocol-0 master; NIP-11 `!Totem motown` markers set+verified; staleness sweep; AGENTS.md device section; totemd session: npub claim moved self→pubkey (spec 02/04/07 + devices), fips watcher slice, aarch64 totemd target; metot catch-up — `!Totem metot` markers + totemd install, fleet symmetric; totemd config + cached NIP-11 prefilter, three-device candidate proof, sync/friendship policy split; signed challenge on totem↔motown (LoadCredential, clock-independent nonce proof, IPv6 bind fix), symmetric recognition + bounded NIP-11 name hints; corrected the display target to `metot`, identified its V4 controller, deployed source-controlled manager configuration, and camera-verified text, image, and raw-frame refreshes; sentinel-based Ansible stack initially converged on physical totem through a swapped `metot` inventory address (later audit corrected inventory/system-arch modeling, challenge/NIP-11 convergence, and docs); VitePress operations/architecture documentation with local-only validation; diagnosed router-vs-master negentropy wire incompatibility, proved filtered bidirectional totem↔motown NIP-77, installed the unprivileged strfry runner, added read-only PiSugar2 UPS telemetry to the device manager, and added a Waveshare UPS HAT (C) driver |
