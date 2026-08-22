# Phase 1 multi-source coverage audit

No planned source item is omitted. This audit covers the roadmap goal, all phase requirements, research constraints/features, and context decisions. Deferred context ideas are explicitly excluded, not silently planned.

## GOAL coverage

| Goal item | Disposition | Plans |
|---|---|---|
| Replace closed device-type/central-registry ownership with an open capability + binding runtime | covered | 01-03–07, 01-23, 01-28 |
| Support an unbounded provider/driver compatibility matrix through import-free discovery, facts, config, and resources | covered | 01-02–07, 01-11–22 |
| Default to process isolation with configurable identical-protocol in-process extensions | covered | 01-08–10 |
| Make the NIP-5D-shaped loopback bus canonical and all old surfaces outward facades | covered | 01-23–32 |
| Preserve local compatibility and defer Pi/default cutover until explicit allocation | covered | 01-25–33; manual gate in 01-33 |

## REQ coverage

All 33 IDs are mapped to concrete plan/tasks and commands in `01-VALIDATION.md`: HWR-01..04, SPI-01..06, CMP-01..04, ISO-01..07, RUN-01..03, API-01..05, and TST-01..04. ISO-02 has exactly one implementation owner, 01-10 Task 1. The deterministic 43-item expansion is independently accounted in `01-PROBE-LEDGER.md`.

## RESEARCH coverage

| Research feature / constraint | Disposition | Plans / evidence |
|---|---|---|
| Independently packaged public API and installable fixture before runtime work | covered | 01-02 Task 1 |
| Import-free distribution-file manifest catalog; selected-host import only | covered | 01-02–05; sentinel/import tests |
| Capability ID + binding identity, facts and data-only profiles; no closed device class tree | covered | 01-03–07, 01-23 |
| Typed TOML/injectable config, exact precedence, affected-binding rejection, credential/file/inherited-descriptor secrets | covered | 01-05; SEC-01/02 |
| Atomic normalized resource broker and complete resolution evidence | covered | 01-06–07 |
| Carrier-neutral NIP-5D logical envelope over bounded framed Unix canonical JSON/attachments | covered | 01-08; SEC-03/04/05 |
| Explicit lifecycle, required readiness, bounded backoff/quarantine, generation isolation, confirmed death before lease release | covered | 01-09; SEC-07; P-S1 |
| Process default and globally/plugin/binding configurable in-process host with identical protocol; contamination semantics | covered | 01-09–10; SEC-08; P-S2 |
| Built-in display, power, NFC, storage, Wi-Fi, Bluetooth providers use the ordinary SPI/hosts | covered | 01-11–22 |
| Radio coexistence as broker data/policy, not hidden manager locks | covered | 01-19–22 |
| One eager runtime, stable handles, loopback bus/SSE | covered | 01-23–24 |
| Screen, REST/WebSocket/env/client, managers, registry/contracts, device wrappers, CLI/systemd are outward only | covered | 01-25–32 |
| Python >=3.9 controlled feedback, fake time/process/socket/broker, vectors, AST dependency test | covered | 01-01; 01-VALIDATION |
| Pi benchmark schema/runbook for armv6l, armv7l, aarch64 without inferred acceptance | covered/deferred physical execution | 01-33; P-S3 |
| Spike findings guide tests/protocol decisions but spike Python is not production code | covered | 01-01–08 import/vector criteria |
| Conditional `tomli` only for Python <3.11 and package legitimacy evidence | covered | 01-01/05; package audit in 01-RESEARCH.md |
| ASVS L1 threat mapping for every phase trust boundary | covered | `01-SECURITY.md`; every plan links applicable SEC rows |

## CONTEXT decision coverage

| Locked decision | Disposition | Implementing plans |
|---|---|---|
| Eager catalog→resolve→claim→start; stable plan/health | covered | 01-03–10, 01-23 |
| Per-binding degradation; required capabilities gate readiness | covered | 01-09, 01-23 |
| Bounded exponential recovery then quarantine; controlled restart applies config/manifest change | covered | 01-09, 01-32 |
| Typed TOML/injection; legacy env only at facade; exact binding→plugin→global→manifest precedence | covered | 01-05, 01-26, 01-32 |
| Invalid config rejects affected binding only; secrets use refs/descriptors and never appear in manifest/messages/diagnostics | covered | 01-05; SEC-01/02 |
| Clean internal break; no hybrid manager/runtime or parallel implementation | covered | 01-23–32 plus AST guard |
| No runtime deprecation warning; preserve outward behavior | covered | 01-25–32 |
| Loopback NIP-5D HTTP result + SSE canonical; REST translates; host IPC reuses logical envelope over Unix carrier | covered | 01-08, 01-23–26 |
| Exactly one startup owner; no legacy/canonical concurrent hardware contact; deployment cutover after allocated Pi acceptance | covered | 01-23, 01-32–33 |
| Agent discretion on internal names/granularity, bounded configurable thresholds, facade mechanics | exercised consistently | module/task boundaries in 01-03–33 |

## Deferred and excluded items

| Deferred item | Disposition |
|---|---|
| Plugin signatures/provenance, non-Python providers, authenticated plugin installation | excluded exactly as context directs; not implemented by any task. Existing package-legitimacy and import-boundary controls do not claim this ecosystem work. |
| Physical Pi execution before allocation | excluded from autonomous execution; Plan 33 creates the harness/runbook and leaves acceptance/cutover manual and deferred. |

Final source audit: **GOAL covered; 33/33 REQ covered; all applicable RESEARCH features/constraints covered; all locked CONTEXT decisions covered; 2/2 deferred ideas excluded with rationale; 0 missing items.**
