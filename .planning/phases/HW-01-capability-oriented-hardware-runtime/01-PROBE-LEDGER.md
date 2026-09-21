# Phase 1 deterministic probe ledger

This ledger is the no-silent-drop authority for the spec-less deterministic edge probe and adversarial prohibition recall. `COVERAGE.md` is intentionally not used because this phase has no external-service API matrix.

## Edge-probe accounting

The deterministic expansion yielded exactly **43 applicable items**: **23 classified probes + 20 unclassified assumptions = 43 accounted**, with **0 dismissed and 0 omitted**. Classified probes are `covered` by explicit acceptance behavior. Unclassified probes remain `flagged assumption` even when a local command supplies useful evidence; only a later explicit contract/evidence decision may resolve them.

| # | Requirement | Category / probe | Disposition | Owning plan/task | Concrete acceptance assertion | Automated/manual verification |
|---:|---|---|---|---|---|---|
| 1 | HWR-03 | concurrency | covered | 01-03 Task 1 | Concurrent catalog/claim requests share one immutable startup snapshot and canonical code imports no provider. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k concurrent -x` |
| 2 | SPI-01 | concurrency | covered | 01-03 Task 1 | Concurrent distribution scans deduplicate to one ordered plugin record with no provider import. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k catalog_concurrent -x` |
| 3 | SPI-02 | concurrency | covered | 01-02 Task 1 | Frozen public message/capability values are reusable by simultaneous callers. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_public_api_fixture.py -k immutable -x` |
| 4 | SPI-04 | concurrency | covered | 01-05 Task 1 | Concurrent config loads publish one immutable typed snapshot and isolate invalid bindings. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_config.py -k concurrent -x` |
| 5 | SPI-05 | concurrency | covered | 01-05 Task 1 | Concurrent secret/config resolution never places secret values in manifests, IPC, logs, or diagnostics. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_config.py -k secret -x` |
| 6 | SPI-06 | concurrency | covered | 01-04 Task 1 | Simultaneous generic requests route through binding identity without driver-specific routers. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_host_bus_tracer.py -k dispatch -x` |
| 7 | ISO-03 | concurrency | covered | 01-08 Task 2 | Concurrent fragmented/pipelined frames remain correlated and bounded. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -k concurrent -x` |
| 8 | RUN-02 | concurrency | covered | 01-07 Task 1 | Contending normalized claims admit one atomic owner and produce deterministic conflict evidence. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_broker.py -k concurrent -x` |
| 9 | RUN-03 | concurrency | covered | 01-19 Task 1 | Compatible radio modes coexist; incompatible shared-PHY modes fail before provider calls. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_radio_resources.py -x` |
| 10 | TST-04 | concurrency | covered | 01-33 Task 2 | Parallel callers/faults create no second owner, leaked worker, or stale generation. | `.venv/bin/python -m pytest tests/unit/test_phase1_regression.py -k concurrent -x` |
| 11 | SPI-01 | adjacency | covered | 01-03 Task 1 | Installing/removing a neighboring distribution affects only the next controlled-start snapshot. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k adjacent_distribution -x` |
| 12 | SPI-01 | empty | covered | 01-03 Task 1 | An empty entry-point group yields a valid empty catalog and structured unavailable result. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k empty_catalog -x` |
| 13 | SPI-01 | ordering | covered | 01-03 Task 1 | Metadata/manifest validation, resolution, and claims finish before selected-child import. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k before_import -x` |
| 14 | SPI-01 | idempotency | covered | 01-03 Task 1 | Unchanged installed distributions produce byte-equivalent ordered snapshots/diagnostics. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_catalog_claim_tracer.py -k idempotent_catalog -x` |
| 15 | ISO-06 | adjacency | covered | 01-10 Task 1 | Changing only one adjacent execution override changes only that binding's host selection. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -k adjacent_override -x` |
| 16 | ISO-06 | empty | covered | 01-10 Task 1 | No override selects the global process default; empty enabled bindings start no host. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -k default_or_empty -x` |
| 17 | ISO-06 | ordering | covered | 01-10 Task 1 | Precedence is explicit binding, plugin, global, manifest, with identical logical transcripts. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -k precedence -x` |
| 18 | RUN-01 | adjacency | covered | 01-09 Task 1 | One optional binding failure degrades only its adjacent capabilities; required failure gates readiness. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py -k adjacent_degradation -x` |
| 19 | RUN-01 | empty | covered | 01-09 Task 1 | An empty enabled plan is ready and starts no host; missing required capability is not ready. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py -k empty_plan -x` |
| 20 | RUN-01 | ordering | covered | 01-09 Task 1 | Enabled bindings transition through declared lifecycle/event order under the fake clock. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_lifecycle.py -k ordering -x` |
| 21 | TST-01 | adjacency | covered | 01-10 Task 2 | Adding one conformance case runs against both hosts without changing host-specific assertions. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py -k adjacency -x` |
| 22 | TST-01 | empty | covered | 01-10 Task 2 | Empty conformance selection reports zero cases without starting a host. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py -k empty -x` |
| 23 | TST-01 | ordering | covered | 01-10 Task 2 | The same normalized transcript/order is asserted for process and in-process hosts. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_conformance.py -k ordering -x` |
| 24 | HWR-01 | unclassified | flagged assumption | 01-06 Task 1 | Capability ID + binding identity remains sufficient primary identity across current and fixture providers. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py -k identity -x`; remains flagged for future provider classes. |
| 25 | HWR-02 | unclassified | flagged assumption | 01-02 Task 1 | Public capability-major compatibility rejects incompatible fixture versions before import. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_public_api_fixture.py -k api_major -x`; remains flagged across independent releases. |
| 26 | HWR-04 | unclassified | flagged assumption | 01-23 Task 1 | One runtime owns catalog, plan, leases, supervisors, health, and events for one application lifespan. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_runtime.py -k sole_owner -x`; deployment composition is rechecked in Plan 32. |
| 27 | SPI-03 | unclassified | flagged assumption | 01-05 Task 1 | Current manifest schema expresses all built-in/fixture compatibility, config, resource, and grouping data without code import. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_manifest.py -k schema -x`; remains flagged for future capabilities. |
| 28 | CMP-01 | unclassified | flagged assumption | 01-06 Task 1 | CPU/OS facts distinguish artifact class from physical architecture and do not imply a device type. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_facts.py -k cpu_os -x`; remains flagged for unseen boards. |
| 29 | CMP-02 | unclassified | flagged assumption | 01-06 Task 1 | Bus/device/interface facts are normalized data and never executable class selectors. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_facts.py -k buses -x`; remains flagged for new kernels. |
| 30 | CMP-03 | unclassified | flagged assumption | 01-06 Task 1 | Optional profiles are data-only overrides/preferences and cannot import or instantiate providers. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py -k profile -x`; remains flagged for future profile fields. |
| 31 | CMP-04 | unclassified | flagged assumption | 01-06 Task 1 | Every candidate includes complete supporting/missing/rejecting evidence with deterministic tie/ambiguity rules. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_resolver.py -k evidence -x`; remains flagged for new evidence vocabularies. |
| 32 | ISO-01 | unclassified | flagged assumption | 01-09 Task 2 | Process mode is the default and selected third-party code imports only after plan/claims in the child. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py -k default_and_import -x`; OS sandbox strength is not assumed. |
| 33 | ISO-02 | unclassified | flagged assumption | 01-10 Task 1 | Global/plugin/binding in-process opt-in uses the identical DriverHost/logical protocol. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_in_process_host.py -x`; trust remains administrator-assumed. |
| 34 | ISO-04 | unclassified | flagged assumption | 01-08 Task 2 | Canonical JSON plus raw attachment descriptors covers current capability payloads within bounds. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_protocol.py -k attachment -x`; codec remains provisional pending Pi evidence. |
| 35 | ISO-05 | unclassified | flagged assumption | 01-09 Task 2 | Provider/binding process grouping remains independently configurable and lease-safe. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py -k grouping -x`; fleet default remains deferred. |
| 36 | ISO-07 | unclassified | flagged assumption | 01-09 Task 2 | Startup/cancel/terminate/kill/backoff/quarantine defaults are bounded, typed, and operationally sufficient locally. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_process_host.py -k deadlines -x`; Pi timing remains deferred. |
| 37 | API-01 | unclassified | flagged assumption | 01-24 Task 1 | The NIP-5D-shaped loopback request/result + SSE surface covers current canonical application needs. | `.venv/bin/python -m pytest tests/unit/test_hardware_bus.py -x`; future application domains remain flagged. |
| 38 | API-02 | unclassified | flagged assumption | 01-19 Task 1 | Public Wi-Fi/Bluetooth boundaries cover PR #22 radio primitives without a monolithic manager contract. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_radio_resources.py -x`; new kernel/backend primitives remain flagged. |
| 39 | API-03 | unclassified | flagged assumption | 01-25 Task 1 | FrameSink, PowerStatus, and HardwareHealth are sufficient screen ports for current behavior. | `.venv/bin/python -m pytest tests/unit/test_screen.py -x`; future screen concerns must justify a new narrow port. |
| 40 | API-04 | unclassified | flagged assumption | 01-32 Task 1 | Current routes/imports/commands/env/unit names preserve semantics without deprecation or silent fallback. | `.venv/bin/python -m pytest tests/unit/test_cli_compat.py tests/unit/test_systemd_contracts.py tests/unit/test_phase1_regression.py -x`; fleet cutover remains deferred. |
| 41 | API-05 | unclassified | flagged assumption | 01-28 Task 1 | The AST/import and fixture-plugin tests express the authoritative clean-break boundary. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_import_boundaries.py tests/unit/test_registry_facade.py -x`; any exception requires a new decision. |
| 42 | TST-02 | unclassified | flagged assumption | 01-06 Task 1 | The current fact/evidence fixture matrix represents all locally testable detection ambiguity. | `.venv/bin/python -m pytest tests/unit/hardware_runtime/test_facts.py tests/unit/hardware_runtime/test_resolver.py -x`; new hardware facts extend the matrix. |
| 43 | TST-03 | unclassified | flagged assumption | 01-33 Task 1 | Benchmark workload/result schema is sufficient to decide grouping/codec defaults only after all three Pi architectures report complete evidence. | Manual deferred gate: allocated armv6l, armv7l, and aarch64 runs per `docs/hardware-driver-benchmark.md`; controller self-test cannot resolve it. |

## Prohibition-recall accounting

Recall yielded **12 candidates = 3 surviving values/safety prohibitions + 6 canon-security breadcrumbs + 3 routine-engineering drops**. No candidate is silent. Surviving entries are intentionally `unresolved`, `verification: null`, and carry no `check_*` descriptor; they therefore remain flagged-unverified rather than receiving a false green.

### Surviving descriptor-less prohibitions

| ID | Requirement | Statement | Disposition | Owning plan/task |
|---|---|---|---|---|
| P-S1 | ISO-01 / RUN-02 | A lease must not be released or reassigned until child death is positively confirmed. | unresolved; verification null; no check descriptor | 01-09 Task 2 |
| P-S2 | ISO-02 | An uncooperative in-process binding must not be described as crash-contained or safely stopped; it becomes CONTAMINATED, rejects work, retains leases, and requires daemon restart. | unresolved; verification null; no check descriptor | 01-10 Task 1 |
| P-S3 | TST-03 | Controller-only tests must not be presented as Pi acceptance, and no bench/deployed default may change without explicit allocation and rollback evidence. | unresolved; verification null; no check descriptor | 01-33 Task 1 |

### Canon-security breadcrumbs (not duplicated as prohibitions)

| ID | Candidate | Disposition and rationale | Security owner |
|---|---|---|---|
| P-C1 | Secret/config value disclosure | Dropped from prohibition list: security canon; explicit controls/tests own redaction and inherited descriptors. | SEC-02 |
| P-C2 | Non-loopback canonical bus/SSE access | Dropped from prohibition list: access-control/security canon with route/bind tests. | SEC-03 |
| P-C3 | Unbounded/malformed Unix frames and attachment lengths | Dropped from prohibition list: input-validation/DoS security canon. | SEC-04 |
| P-C4 | Storage/socket filesystem traversal or unsafe path scope | Dropped from prohibition list: filesystem validation/security canon. | SEC-05 |
| P-C5 | Excess D-Bus/device/resource/child privileges | Dropped from prohibition list: least-privilege/security canon; process isolation is not relabeled a sandbox. | SEC-06 |
| P-C6 | Untrusted dependency/provider provenance | Dropped from prohibition list: supply-chain security canon; package legitimacy and import boundary own it. | SEC-01 / SEC-06 |

### Routine-engineering drops

| ID | Candidate | Disposition and rationale |
|---|---|---|
| P-R1 | Do not mutate caller-owned messages/config | Dropped: routine immutability/correctness, already covered by frozen-value and config tests; not a values/safety prohibition. |
| P-R2 | Do not leak ordinary file/socket/task handles | Dropped: routine lifecycle/resource correctness, already covered by process/protocol/final regression tests. |
| P-R3 | Do not reorder or duplicate deterministic work | Dropped: the deterministic edge probe already owns ordering/idempotency rows; duplicating it as a prohibition would double-count. |

## Per-plan surviving-prohibition proof

This table is the authority allowing an empty `must_haves.prohibitions` array: `none` means recall found no surviving values/safety prohibition for that plan after the canon/routine precision pass.

| Plan | Survivor |
|---|---|
| 01-01 | none |
| 01-02 | none |
| 01-03 | none |
| 01-04 | none |
| 01-05 | none |
| 01-06 | none |
| 01-07 | none |
| 01-08 | none |
| 01-09 | P-S1 |
| 01-10 | P-S2 |
| 01-11 | none |
| 01-12 | none |
| 01-13 | none |
| 01-14 | none |
| 01-15 | none |
| 01-16 | none |
| 01-17 | none |
| 01-18 | none |
| 01-19 | none |
| 01-20 | none |
| 01-21 | none |
| 01-22 | none |
| 01-23 | none |
| 01-24 | none |
| 01-25 | none |
| 01-26 | none |
| 01-27 | none |
| 01-28 | none |
| 01-29 | none |
| 01-30 | none |
| 01-31 | none |
| 01-32 | none |
| 01-33 | P-S3 |

Final equality: **43 edge items accounted exactly once; 12 prohibition candidates accounted exactly once; 0 dismissed edge items; 0 omitted items.**
