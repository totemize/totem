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
| [2026-08-21 — CoC and Wi-Fi Aware radio substrate](journal/2026-08-21.md#coc-and-wi-fi-aware-extension-for-the-radio-substrate) | Rebased PR #22 on master; added typed CoC/NAN capabilities, bounded payload-blind CoC with assigned-PSM advertising and FIPS FD handoff, upstream-iw NAN discovery, honest unsupported Linux NDP reporting, mocks and local tests; no device testing while hardware is unallocated. |
| [2026-08-20 — static Svelte web app](journal/2026-08-20.md#totemd-static-svelte-web-app) | Replaced the SSR root with embedded Svelte 5/Vite; retained NIP-98 controls; added public aggregate and owner-signed live state without exposing the bus; deployed to totem, then added a nos2x LAN-HTTP bridge and deployed it to motown with claimed profile preserved. |
| [2026-08-20 — e-ink boot POC](journal/2026-08-20.md#e-ink-boot-presentation-state-machine) | Fleet-generic screen artifacts with inventory-gated activation; composable boot presentation service; synthetic replay and real reboot camera verification on metot; cross-layer Totem state catalog and display arbitration model. |
| [2026-08-20 — periodic reconciliation](journal/2026-08-20.md#totemd-periodic-reconciliation-and-event-history) | Added bounded event history, five-minute non-overlapping NIP-77 rounds, and readable per-round reconciliation summaries with optional set-difference counts. |
| [2026-08-20 — radio primitives](journal/2026-08-20.md#policy-free-device-manager-radio-primitives) | Capability-complete policy-free Wi-Fi/P2P/Bluetooth/BLE/GATT device-manager surface; least-privilege Ansible integration; live totem↔metot P2P group and bidirectional packets; BLE scan proof and BlueZ 6.18 advertising limitation. |
| [2026-08-19](journal/2026-08-19.md) | FIPS bring-up triage on totem; metot onboarding; mesh detection checks (ping, DNS, NIP-11 both directions); LAN-vs-mesh benchmark; nak armv6 build + cross-relay NIP-77 sync (host & device-side); nostr-ops benchmark: publish + negentropy via nak vs `strfry sync` (14×/80×/11× — daemon will orchestrate strfry sync); spec: radio modes + `!Totem` AP conventions; AGENTS.md created; repo reduced to Python hw stack (PR #9); totemd design session — control plane specced (`spec/10`): no relay proxy, marker via NIP-11 `name`/`self`, challenge on web port, NIP-5D bus over loopback HTTP/SSE, totemctl client; versioned E-ink drivers deployed and initial screenless-totem electrical triage recorded (corrected on 2026-08-20) |
| [2026-08-20](journal/2026-08-20.md) | motown onboarding (test unit #3, aarch64): mDNS discovery, ssh alias + passwordless key; fips bring-up — aarch64 musl cross recipe (gnu blocked by libdbus-sys), totem-mirrored deploy, mDNS auto-pair, mesh verified (ping/DNS/ssh); initial strfry aarch64 build/deploy, later found wire-incompatible and upgraded to protocol-0 master; NIP-11 `!Totem motown` markers set+verified; staleness sweep; AGENTS.md device section; totemd session: npub claim moved self→pubkey (spec 02/04/07 + devices), fips watcher slice, aarch64 totemd target; metot catch-up — `!Totem metot` markers + totemd install, fleet symmetric; totemd config + cached NIP-11 prefilter, three-device candidate proof, sync/friendship policy split; signed challenge on totem↔motown (LoadCredential, clock-independent nonce proof, IPv6 bind fix), symmetric recognition + bounded NIP-11 name hints; corrected the display target to `metot`, identified its V4 controller, deployed source-controlled manager configuration, and camera-verified text, image, and raw-frame refreshes; sentinel-based Ansible stack initially converged on physical totem through a swapped `metot` inventory address (later audit corrected inventory/system-arch modeling, challenge/NIP-11 convergence, and docs); VitePress operations/architecture documentation with local-only validation; diagnosed router-vs-master negentropy wire incompatibility, proved filtered bidirectional totem↔motown NIP-77, installed the unprivileged strfry runner, deployed the automatic per-encounter supervisor (motown 0→402 events with exact totem ID-set equality), added PiSugar2 and Waveshare UPS HAT (C) telemetry, then completed/converged the current stack on physical metot with Zig cross-build and content-addressed source fixes, shipped the no-script read-only HTML landing page over LAN + mesh, then added motown-only first-signer owner claim, nonce-bound NIP-98 policy/profile controls, device-signed kind 0, hot-reloaded dynamic NIP-11 naming, resilient NIP-07 detection, and an in-memory development nsec signer |
