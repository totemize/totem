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
| [2026-08-21 — totem display enablement](journal/2026-08-21.md#totem-display-enablement) | Enabled the same V4 screen profile on the older totem host, fixed fresh-screen deployment ordering, camera-verified the live UI, and converged with `changed=0`. |
| [2026-08-21 — state-specific word-reveal captions](journal/2026-08-21.md#state-specific-word-reveal-captions) | Added stable randomized captions for all 13 authoritative scenes, independent word timing, exhaustive deterministic proof, and [physical metot evidence](proofs/2026-08-21/state-captions/README.md). |
| [2026-08-21 — authoritative footer note count](journal/2026-08-21.md#authoritative-footer-note-count) | Replaced the friend star with `[•]`, added the cached kind-1 note count at bottom right, and physically verified live `404` rendering on metot. |
| [2026-08-21 — interactive face animations](journal/2026-08-21.md#authoritative-interactive-face-animations) | Added state-bound idle, charging, sync, suspicious-peer, and flirty-candidate motion; deterministic 49-frame replay and [camera proof](proofs/2026-08-21/interactive-animations/README.md) passed on metot with a fixed left-side glasses sequence. |
| [2026-08-21 — V4 e-ink quality](journal/2026-08-21.md#waveshare-v4-contrast-and-flash-correction) | Hardware A/B on metot identified the old-plane rewrite as the contrast regression; the Pwnagotchi-compatible partial waveform stayed crisp through 201 updates with no scheduled full flash. |
| [2026-08-20 — runtime face renderer](journal/2026-08-20.md#totem-runtime-face-renderer-and-v4-partial-refresh) | Added the authoritative 28-frame runtime projection, durable recognition history, cancellation tombstones, efficient V4 partial refresh with cadence 20, metot-only convergent deployment, and [physical camera proof](proofs/2026-08-20/totem-renderer/README.md). |
| [2026-08-20 — periodic reconciliation](journal/2026-08-20.md#totemd-periodic-reconciliation-and-event-history) | Added bounded event history, five-minute non-overlapping NIP-77 rounds, and readable per-round reconciliation summaries with optional set-difference counts. |
| [2026-08-20 — e-ink boot POC](journal/2026-08-20.md#e-ink-boot-presentation-state-machine) | Fleet-generic screen artifacts with inventory-gated activation; composable boot presentation service; synthetic replay and real reboot camera verification on metot. |
| [2026-08-19](journal/2026-08-19.md) | FIPS bring-up triage on totem; metot onboarding; mesh detection checks (ping, DNS, NIP-11 both directions); LAN-vs-mesh benchmark; nak armv6 build + cross-relay NIP-77 sync (host & device-side); nostr-ops benchmark: publish + negentropy via nak vs `strfry sync` (14×/80×/11× — daemon will orchestrate strfry sync); spec: radio modes + `!Totem` AP conventions; AGENTS.md created; repo reduced to Python hw stack (PR #9); totemd design session — control plane specced (`spec/10`): no relay proxy, marker via NIP-11 `name`/`self`, challenge on web port, NIP-5D bus over loopback HTTP/SSE, totemctl client; versioned E-ink drivers deployed and initial screenless-totem electrical triage recorded (corrected on 2026-08-20) |
| [2026-08-20](journal/2026-08-20.md) | motown onboarding (test unit #3, aarch64): mDNS discovery, ssh alias + passwordless key; fips bring-up — aarch64 musl cross recipe (gnu blocked by libdbus-sys), totem-mirrored deploy, mDNS auto-pair, mesh verified (ping/DNS/ssh); initial strfry aarch64 build/deploy, later found wire-incompatible and upgraded to protocol-0 master; NIP-11 `!Totem motown` markers set+verified; staleness sweep; AGENTS.md device section; totemd session: npub claim moved self→pubkey (spec 02/04/07 + devices), fips watcher slice, aarch64 totemd target; metot catch-up — `!Totem metot` markers + totemd install, fleet symmetric; totemd config + cached NIP-11 prefilter, three-device candidate proof, sync/friendship policy split; signed challenge on totem↔motown (LoadCredential, clock-independent nonce proof, IPv6 bind fix), symmetric recognition + bounded NIP-11 name hints; corrected the display target to `metot`, identified its V4 controller, deployed source-controlled manager configuration, and camera-verified text, image, and raw-frame refreshes; sentinel-based Ansible stack initially converged on physical totem through a swapped `metot` inventory address (later audit corrected inventory/system-arch modeling, challenge/NIP-11 convergence, and docs); VitePress operations/architecture documentation with local-only validation; diagnosed router-vs-master negentropy wire incompatibility, proved filtered bidirectional totem↔motown NIP-77, installed the unprivileged strfry runner, deployed the automatic per-encounter supervisor (motown 0→402 events with exact totem ID-set equality), added PiSugar2 and Waveshare UPS HAT (C) telemetry, then completed/converged the current stack on physical metot with Zig cross-build and content-addressed source fixes, shipped the no-script read-only HTML landing page over LAN + mesh, then added motown-only first-signer owner claim, nonce-bound NIP-98 policy/profile controls, device-signed kind 0, hot-reloaded dynamic NIP-11 naming, resilient NIP-07 detection, and an in-memory development nsec signer |
