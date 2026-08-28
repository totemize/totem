# What we learned from microduck, and how it applies to totem

Source: `references/microduck` @ `590b986` (2026-08-27). Surveyed 2026-08-28 —
two passes: the design docs (`docs/design/`), then the code itself
(`duck-ipc-proto`, `updater`, `robotd`, `duck-control`, `configd`, `btd`,
`xtask`, `test-support`, CI).

This is a working reference, not a narrative. Principles first, then the
borrow list with status — iterate the status as totem evolves. File paths
point into `references/microduck/` so a claim can be checked at the source.

What microduck is: a consumer biped robot (~90k lines Rust, 942 tests), seven
daemons on one board, JSON-RPC 2.0 NDJSON over unix sockets. Everything is
organized around one goal — **never brick a robot in someone's home**. Totem
is not that product, but the engineering disciplines transfer.

---

## Principles (transfer regardless of architecture)

### 1. Make the broken state unrepresentable

Their invariants are compile errors, not prose:

- `duck-control/src/safety.rs` — safety owns *the only write handle* to the
  motors; "enforced by the borrow checker rather than by a rule someone has
  to remember when adding the eighth skill the night before a demo."
- `btd/src/route.rs` — the BLE permission match is exhaustive with **no
  wildcard**: adding a `Call` variant fails to compile until someone decides
  whether BLE may carry it.
- `deny_unknown_fields` on every params type — typos fail loudly, unknown
  wire members are refused *naming the member*.
- `duck-ipc-proto` depends on serde + semver only, so recovery-path daemons
  cannot inherit the updater's http/tar/crypto tree.
- `xtask` links `minisign` (can sign); the robot links `minisign-verify`
  only (cannot). Trust arranged in the dependency graph.

**Totem application:** owner-only/public/loopback authz over bus and web
methods as one exhaustive match; `deny_unknown_fields` on config structs.
See borrow list B1/B2.

### 2. The recovery path must survive the core being dead

`configd`, `updaterd`, `btd` start, run, and stay useful when `robotd` is
crashed/looping/absent — because "a robot whose control loop won't start is
exactly the robot someone needs to reconfigure, update, or roll back"
(`docs/design/architecture.md` §1.1). No systemd `Requires=` on the core;
every cross-service call optional and timeout-bounded; minimal dependency
surface on the recovery trio. Corollary: nothing that can *refuse* belongs
in the recovery path (rollback/reset must never be gated).

**Totem application:** we already have this de facto — fips and strfry share
no fate with totemd — but it is unstated, so nothing protects it. Write the
invariant down before the kernel work multiplies processes (B4).

### 3. Swapped releases, never patched

Versioned dirs `releases/<ver>/`, atomic `rename(2)` of a `current` symlink,
health gate after the swap, auto-rollback, a golden release never pruned, a
boot counter for "won't start", and a boot-time rescue that lives *outside*
the daemon (because the failure it exists for is an updater that won't
start). Whole state rule in one sentence: **everything outside
`releases/<ver>/` survives both an update and a rollback.**
(`docs/design/updater-design.md`)

**Totem application:** B3 — layout in flash.sh now, engine never (SSH fleet).

### 4. The decoder is the gate; the version number is a label

They shipped an exact-match protocol-version gate, learned it was wrong
("a gate fired on every call, including `update apply` — which is how a skew
ends"), and evolved to: a bump promises nothing in either direction; no
daemon refuses a call because the number differs. What refuses instead:
unknown method → `METHOD_NOT_FOUND` by name; unknown params member →
`INVALID_PARAMS` naming the member. Killer case for silent-ignore (v7): a v6
daemon would have accepted `--from <dir>` and *quietly installed from its
configured source* — "silence was the danger, not disagreement."
(`duck-ipc-proto/src/lib.rs`, `API_VERSION` doc)

**Totem application:** bus params reject unknown fields by name; integer
version in `totem.status.get` as a label only (B5).

### 5. Failure paths need fault injection, because they only run when something already went wrong

`updater/src/faults.rs` — injectable failures compiled into the shipping
binary (flag-gated, never set in prod): corrupt artifact, fail hook,
hang health, `abort_after_swap` (kill -9 mid-swap), `fail_rollback`
(worst path: failed update *and* failed recovery). Fixtures
(`test-support`) sign with the same minisign/tar/zstd crates the engine
verifies with — "a fixture cannot produce an artifact the real code rejects
for a reason the fixture invented."

**Totem application:** when sync/pairing code is next touched, leave a
`--fault` seam: peer departs mid-round, challenge hangs, relay wedged (B6).

### 6. Forcing-function tests for drift

Their tests fail when: `install.sh` grows a step hooks don't perform
(got wrong four times — `docs/project/install-path-gap.md`); a params key
misses the machine-readable registry; a hook script isn't packaged;
`NEVER_RESTART` ≠ `RESTART_AFTER_REPLYING`; a curl-fetched script's version
literal disagrees with `workspace.metadata`. The pattern: when two copies of
a truth must agree, a test forces the agreement instead of a comment hoping
for it.

**Totem application:** we have three deploy paths (flash.sh / Ansible /
factory-reset) and a spec-10 config table with the same exposure (B7).

### 7. Comments carry measurements and failure stories

Not "what" but *why, what it cost, what the wrong version did*: the
43.1 Hz-vs-50 Hz `MissedTickBehavior::Delay` bug; 3s peer staleness; the
four install-path gaps; the v7 silence. And `restart-order.md`: "read from
the code; where a narrative comment disagrees with this page, the comment
is the bug."

**Totem application:** journal keeps the story (good); code comments should
link to the journal entry when a decision is non-obvious, because the
journal isn't open at 3am (B8).

---

## Borrow list

Status legend: ☐ todo · ◐ partial · ☑ done · ✗ decided against.

| # | What | Effort | Status |
|---|------|--------|--------|
| B1 | Exhaustive-match authz table in totemd: one enum of all bus/web methods, match by class (public / owner-only / loopback-only), no wildcard arm. New method without a class = compile error. | ~half day | ☐ |
| B2 | `deny_unknown_fields` on totemd config + bus params structs; refusals name the field. | ~1 h | ☐ |
| B3 | Release layout in flash.sh: `/opt/totem/releases/<rev>/totemd`, `current` symlink, unit points through `current`, swap + health check (`totemctl status`) + rollback + keep-previous. No engine, no signatures yet — just the on-disk contract. | ~half day | ☐ |
| B4 | Two invariants into spec 10: (a) fips and strfry MUST NOT depend on totemd, totemd MUST NOT become load-bearing for mesh or relay; (b) state rule — everything outside `releases/<ver>/` survives update and rollback; recovery/reset paths never refuse. | paragraphs | ☐ |
| B5 | Bus version discipline per principle 4: integer `api_version` in `totem.status.get` as a label; strict params decode as the actual gate. Documented in spec 07. | ~1 h + spec | ☐ |
| B6 | Fault-injection seam in sync/pairing (`--fault` flags, test-only): peer-depart mid-round, challenge hang, relay wedge. Ship-in binary like theirs so a bench unit can exercise it. | when next in sync.rs | ☐ |
| B7 | Drift tests: (a) flash.sh / Ansible / factory-reset agree (steps one does, the others that must know about do); (b) spec-10 config table ↔ config struct field walk. Escape hatch = written line with a reason, like theirs. | ~a day | ☐ |
| B8 | Build identity: `TOTEM_REVISION` compiled in (CI sets it; local says `rev unknown, not a CI build`), totemd first log line at `warn` with version/revision/`exe=` from `/proc/self/exe`; identity published to `/run/totemd/identity.json` (RuntimeDirectory, so stale identities cannot outlive the unit; never fatal to start). | ~2 h | ☐ |
| B9 | Later, when releases are signed: tiered key custody — multiple trusted public keys from day one, spares differing in passphrase *and* exposure; unretrofittable manifest fields (`min_supported`) present from the first release even if unused. | at signing time | ☐ |

## Convergence — already right, do not churn

- **Single writer**: totemd is the only kind-3 writer; their rule, already ours.
- **Recovery path exists**: fips + strfry independent of totemd (just unstated — B4).
- **Typed events, not logs**: spec 10 already says peripherals react to typed bus events; same conclusion as their "features, not frames".
- **Bus over loopback HTTP/SSE, not unix sockets**: different threat model. Their socket reasoning (SO_PEERCRED, "0.0.0.0 by typo" unrepresentable) is right for *them*; ours is right for the NAP/web-projection seed. Keep.
- **Transports owned by one layer**: fips owns ours the way NetworkManager owns their wifi. Both the lazy, correct call.
- **Group/permission discipline in units**: strfry group, fips group — same conclusion as their `Group=robot` ("load-bearing, not cosmetic").

## Decided against

- **Seven-daemon split.** Justified by motors and media weight; we have no actuators beyond a slow e-ink panel. totemd + strfry + fips + totem-screen is the right grain.
- **Their updater engine** (18k lines: manifests, sources, boot counters, rescue). SSH fleet of three; the layout (B3) buys the future, the engine would be cosplay now.
- **Their closed owner model** (pairing PIN, authority arbitration). Totem is open/multi-user by principle; NIP-98 claim is our own answer.
- **WebRTC/mediad, BLE, apt repo** — N/A.

## Open questions to keep alive (from this study)

1. **Mesh-distributed updates.** Their zero-backend choice is GitHub Releases
   over each robot's wifi. A signed release artifact is just data, and totems
   already reconcile data with NIP-77 on encounter — an update that
   propagates peer-to-peer, carried physically, is the same sneakernet story
   applied to the fleet. Verification is per-artifact (their "promotion =
   re-signing the same bytes" shows why per-hop trust is unnecessary).
   Belongs in `spec/09-open-questions.md`; not designed until units leave
   the bench.
2. **Mixed-version mesh is the norm, not the edge.** Their assumption
   "every binary on a board comes from one release" is false the day two
   people carry totems running different versions. Rule for spec 03:
   peers that don't understand a marker/intent are *listened to, not argued
   with* — the protocol never requires version symmetry to make progress.
   Their chorale models the degradation: a duck that doesn't know a piece
   id "keeps listening rather than joining... an old duck near new ones
   stays politely quiet." Our NIP-11 prefilter TTL already behaves this way.
3. **Deterministic leader for synchronized exchanges.** If any future
   totem↔totem exchange needs a conductor (their chorale, `robotd/chorale.rs`):
   "the lower id conducts — deterministic, so there is no election to go
   wrong and no message to lose." Lower npub conducts; no negotiation.

## Patterns worth remembering (no action, recall when relevant)

- **Read-only answers during mutation**: engine behind a mutex; readers
  `try_lock` + fall back to a cached snapshot; progress via broadcast where
  "a client that can't keep up gets a gap, never backpressure onto the
  update" (`updater/src/ipc.rs`). If `totemctl status` ever blocks on a sync
  round, this is the fix.
- **Timestamped last-value-wins slots** (`robotd/src/intents.rs`, ArcSwap):
  "the loop's real question is never 'what is the value' but 'how old is
  it'". Separate slots per intent kind so two writers can't lose each
  other's updates in read-modify-write.
- **Transports forward verbatim** (`btd/src/session.rs`): parse only enough
  to answer "allowed here?" and "who owns it?"; never re-serialize params.
  That's what keeps a transport from becoming a second implementation of
  the API — adding a method costs one line in one table.
- **Identity + reconcile** (`duck-ipc-proto::Identity`, `updater/src/reconcile.rs`):
  daemons publish `/run/<svc>/identity.json`; a supervisor compares each
  unit's identity to the active release on start and restarts the stale,
  because "scheduling a restart is not evidence that one happened." Exception:
  the supervisor never restarts *itself* (loop risk) — the check is reached
  from the other side instead.
- **Config schema as its own crate for the editor** (`robotd-params`):
  `robotctl configure` edits against the real schema — "doing that against
  a copied schema is how a copied schema drifts"; registry completeness
  enforced by walking the struct's serialization. And config is read once,
  never watched — "an editor never has to ask which keys are live."
- **CLI duality** (`robotctl monitor`): TUI on a terminal, NDJSON when
  piped — "a screen-painting CLI that writes escape codes into a log file
  is a CLI nobody can script."
- **An unprivileged daily client keeps the API honest** (`padd`): the intent
  API "cannot quietly rot the way an API only the phone app uses inevitably
  would." totemctl is ours; keep exercising it in every deploy/verify.
- **dev-push runs the full gated path** — no bypass flag; a dev key instead,
  so even laptop builds get preflight/verify/health-gate/rollback.
