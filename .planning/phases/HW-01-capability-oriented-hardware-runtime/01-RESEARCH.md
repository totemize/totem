# Phase 1: Capability-Oriented Hardware Runtime - Research

**Researched:** 2026-08-22  
**Domain:** Python 3.9 hardware-plugin runtime, process supervision, and local NIP-5D-shaped messaging  
**Confidence:** HIGH for the target contract and local migration seams; MEDIUM for production performance/security limits pending Pi acceptance.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Runtime Startup and Recovery
- Catalog, resolve, claim resources, and eagerly start every enabled binding at
  runtime startup so callers receive a stable binding plan and health snapshot.
- A failed binding degrades the runtime without disabling unaffected
  capabilities. Only capabilities explicitly configured as required make
  overall readiness fail.
- Use bounded exponential restart backoff followed by quarantine with
  actionable diagnostics. Manual intervention or a controlled service restart
  clears quarantine.
- Treat manifests and runtime configuration as startup-bound in v1. Apply
  changes through a controlled daemon restart so binding and resource changes
  are atomic.

### Configuration and Overrides
- Use typed TOML-backed runtime configuration with directly injectable
  configuration objects for tests. Existing environment variables are parsed
  only by legacy compatibility adapters.
- Apply precedence in this order: explicit component binding, per-plugin
  settings, global runtime defaults, then manifest defaults.
- Reject an affected binding on invalid or unknown configuration with
  structured diagnostics; do not silently ignore the setting and do not fail
  unrelated bindings or the whole daemon.
- Supply secrets through credential/file references or inherited descriptors.
  Secrets never appear in manifests, driver messages, or diagnostics.

### Compatibility and Cutover
- Make a clean internal break: implement the new canonical runtime directly,
  without hybrid manager/runtime internals or parallel implementations.
  Existing managers survive only as thin boundary facades over capability
  handles and the bus.
- Do not emit runtime deprecation warnings for legacy paths in v1. Preserve
  their behavior and document their compatibility-facade status.
- Make the canonical application surface the loopback-only NIP-5D-shaped bus:
  HTTP request/result plus SSE pushes, following the `totemd` pattern. Existing
  REST routes translate to bus messages. Driver-host IPC uses the same logical
  envelopes over the bounded framed Unix-socket carrier.
- Select exactly one hardware runtime at service startup. Legacy and canonical
  owners must never touch the same hardware concurrently. Switch deployed
  defaults only after acceptance on explicitly allocated Pi-class hardware.

### the agent's Discretion
- Choose internal module granularity, concrete type names, and implementation
  sequencing within the accepted package/dependency hierarchy.
- Choose documented initial backoff and quarantine thresholds, provided they
  are bounded, deterministic in tests, and configurable without changing
  capability contracts.
- Choose facade implementation mechanics so long as canonical runtime code
  never imports through a legacy facade.

### Deferred Ideas (OUT OF SCOPE)

- Plugin signatures/provenance, non-Python providers, and authenticated plugin
  installation remain v2 ecosystem work.
- Pi-class acceptance is required before deployment cutover, but physical
  execution waits for explicit bench allocation rather than being inferred
  from autonomous mode.
</user_constraints>

## Summary

The implementation should add a **new canonical** `totem.hardware` runtime and
an independently distributable `totem_driver_api` package, then turn the
current `totem.devices`, `totem.managers`, `totem.api`, and screen HTTP client
into outward-facing adapters.  Do not progressively make a manager partly own
a driver and partly call the runtime: the runtime owns catalog, inventory,
resolution, leases, lifecycle, hosts, health, and events from the first
canonical startup.  This is necessary because the current API owns a fixed
five-manager factory map and lazy manager lifecycle, while per-family
`DriverRegistry` instances import allow-listed drivers directly
([VERIFIED: `src/totem/api/app.py`], [VERIFIED: `src/totem/devices/registry.py`]).

Use the existing local NIP-5D convention as the logical API, not as a claim
that the Python runtime is part of `totemd`: `POST /bus` receives a JSON object
and returns `{type: "<request>.result", id?, ok, ...}`, while `/bus/events`
is a lossy loopback SSE stream.  The same schema crosses to isolated hosts on
a framed Unix socket.  The spike validates canonical JSON control frames,
bounded raw attachments, host generations, and a dual-host conformance shape;
it does **not** establish Pi limits or least-privilege sandboxing
([VERIFIED: `spec/07-conventions.md`], [VERIFIED: `totemd/src/bus.rs`],
[VERIFIED: `.codex/skills/spike-findings-totem/references/driver-ipc.md`],
[VERIFIED: `.codex/skills/spike-findings-totem/references/dual-host-lifecycle.md`]).

**Primary recommendation:** implement the public SPI, manifest catalog,
resolver/broker, protocol/hosts, and conformance fixtures before converting a
single built-in provider; then move all built-ins through that one path and
make legacy managers/routes only translators over capability handles.

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|---|---|---|---|
| Versioned contracts, manifest schema, errors | `totem_driver_api` public package | plugin distributions | Third parties must not import runtime/FastAPI/manager internals. |
| Installed-distribution catalog | `totem.hardware.catalog` | `importlib.metadata` | Metadata/manifest validation must happen before plugin import. |
| Hardware evidence and matching | `totem.hardware.discovery` | data-only profiles | Facts and profiles select bindings; no closed subclass/device switch. |
| Binding plan, leases, health, lifecycle | `totem.hardware.runtime` | hosts | One owner must make all start/stop/conflict decisions. |
| Execution/failure boundary | `totem.hardware.hosts` | provider executable | Process host contains child crashes; in-process host advertises contamination. |
| Capability actions and events | `totem.hardware.capabilities` | driver API schemas | Applications bind stable capabilities, never driver IDs/models. |
| Loopback bus and legacy REST | `totem.hardware.api` | legacy `totem.api` facade | Bus is canonical; REST maps old request/response shapes to bus messages. |
| E-ink presentation/boot workflow | `totem.screen` | narrow bus client ports | Screen needs frame sink, power status, and hardware health, not a manager. |
| Existing Python/CLI/systemd interfaces | `totem.devices`, `totem.managers`, `totem.api` | deployment units | Compatibility is outward-only and must never feed back into canonical runtime. |

## Project Constraints (from AGENTS.md)

- Preserve the repository's Python hardware runtime, its tests, and deployment
  units; reference checkouts under `references/` are read-only.
- Keep Python 3.9 compatibility.  The current project requires `>=3.9,<4.0`
  and tests use `pytest` unit/mock-transport/hardware markers
  ([VERIFIED: `pyproject.toml`]).
- Do not touch the bench devices without explicit allocation.  Hardware tests
  are intentionally opt-in through `--run-hardware`
  ([VERIFIED: `tests/conftest.py`], [VERIFIED: `01-CONTEXT.md`]).
- Preserve `totem`, `totem-api`, `totem-screen`, `totem.service`, and
  `totem-screen.service`; current environment names are compatibility inputs,
  not new canonical runtime configuration
  ([VERIFIED: `pyproject.toml`], [VERIFIED: `deploy/systemd/*.service`]).
- Do not expose/copy credentials.  Config and IPC carry references or inherited
  descriptors only; diagnostics redact values.

## Standard Stack

### Core

| Library / facility | Version | Purpose | Why standard here |
|---|---:|---|---|
| `totem_driver_api` (new first-party distribution) | `1.x` | Stable IDs, manifests, messages, capability protocols, lifecycle/errors/resources, conformance helpers | Separates third-party drivers from daemon-private modules, satisfying SPI-01/02. |
| Python stdlib `importlib.metadata` | Python 3.9 | Enumerate installed entry points/distribution files without importing providers | It supports import-free cataloging; actual entry-point loading is deferred to the chosen host. |
| Python stdlib `socket`, `struct`, `json`, `hashlib`, `subprocess` | Python 3.9 | Unix-socket framed canonical JSON carrier, checksums, child supervision | Spike v1 candidate avoids a new codec dependency and executable serialization. |
| Pydantic already in project | `>=2.6,<3.0` | HTTP/bus request validation and typed configuration validation | Existing FastAPI models establish the project pattern ([VERIFIED: `pyproject.toml`], [VERIFIED: `src/totem/api/models.py`]). |
| `tomli` backport | proposed `>=2,<3` | Parse startup TOML on Python 3.9 | Python 3.9 has no `tomllib`; this is the smallest non-hand-rolled parser. **Package gate:** the local legitimacy seam marked it `SUS` only because download metadata was unavailable, so a planner must add a human-verify checkpoint before adding it. [ASSUMED] |

### Supporting

| Facility | Purpose | When to use |
|---|---|---|
| Existing explicit mock transports | Deterministic providers and fault injection | All resolver/host/API tests; no connected hardware. |
| FastAPI + SSE response support | Loopback `/bus` and `/bus/events` | Canonical daemon bus only; existing REST stays translators. |
| `asyncio` + worker threads | Bus-to-sync facade adaptation | Keep synchronous legacy drivers off FastAPI's event loop until replaced by host calls. |
| systemd service manager | Whole-daemon recovery after an in-process native fatality | Do not claim an in-process host contains process-fatal plugin behavior. |

### Alternatives considered

| Instead of | Could use | Decision / tradeoff |
|---|---|---|
| Canonical JSON + raw attachments | MessagePack | Reserve codec ID 2 but do not add it to v1: local spike saved only 47 bytes on the representative frame and Python 3.9/arm packaging is a concern ([VERIFIED: `references/driver-ipc.md`]). |
| Provider process group default | Per-binding default | Provider grouping is the provisional default because it amortizes interpreter cost; expose per-binding as a binding override for smaller crash domains, pending Pi PSS validation ([VERIFIED: `references/process-topology.md`]). |
| `subprocess.Popen` executable host | `multiprocessing` | Do not use `multiprocessing`/pickle at the SPI boundary; it would import/serialize Python objects across the boundary ([VERIFIED: `references/process-topology.md`]). |
| Typed TOML + injected config | environment parsing in runtime | Environment parsing remains only in legacy facades; it cannot express safe precedence/diagnostics. |

### Package Legitimacy Audit

| Package | Registry | Verdict | Disposition |
|---|---|---|---|
| `tomli` | PyPI | `SUS` (local package-legitimacy seam: unavailable download statistic) | Flagged: human verify its official repository/release before adding; no install is authorized by this research. |

No other dependency is required for the phase's core protocol or supervision.

## Architecture Patterns

### System architecture diagram

```text
installed distribution metadata + manifest files      startup TOML + injected test config
                 |                                                 |
                 v                                                 v
         Catalog (no EntryPoint.load) -----> validate -----> RuntimeConfig
                 |                                  \                |
                 v                                   \               v
hardware inventory/facts --> Resolver --> BindingPlan --> ResourceBroker --> leases
                                               |                            |
                                               v                            v
                                      Supervisor / one owner ----> lifecycle + health/events
                                               |
                         +---------------------+----------------------+
                         |                                            |
                         v                                            v
                 ProcessDriverHost (default)                InProcessDriverHost (opt-in)
                 framed Unix socket, child                  same schema/correlation port
                         |                                            |
                         +-------------- NIP-5D envelopes ------------+
                                               |
                                               v
                           canonical loopback POST /bus + SSE /bus/events
                                               |
              +--------------------------------+-------------------------------+
              |                                |                               |
              v                                v                               v
     capability clients/screen           legacy REST translators        legacy import facades
```

### Recommended project structure

```text
packages/totem-driver-api/
  pyproject.toml
  src/totem_driver_api/
    identifiers.py          # CapabilityId, plugin/binding IDs, version parsing
    manifest.py             # data-only manifest + schema validation
    messages.py             # JSON logical envelope, errors, attachments metadata
    lifecycle.py            # public provider/session lifecycle vocabulary
    resources.py            # claim declarations, no broker implementation
    capabilities/           # narrow versioned capability protocols/schemas
    conformance/            # reusable provider/host contract cases

src/totem/hardware/
  catalog/{metadata.py, manifests.py, diagnostics.py}
  discovery/{facts.py, inventory.py, profiles.py, resolver.py}
  runtime/{config.py, bindings.py, broker.py, lifecycle.py, supervisor.py, events.py}
  hosts/{protocol.py, unix.py, process.py, in_process.py, worker.py}
  capabilities/{display.py,power.py,storage.py,nfc.py,radio/{wifi.py,bluetooth.py,shared.py}}
  api/{bus.py, events.py, health.py, legacy_routes.py, app.py}
  builtin/                  # first-party provider packages/manifests, same catalog path

src/totem/{devices,managers,api}/  # boundary-only compatibility facades
src/totem/screen/ports.py          # FrameSink, PowerStatus, HardwareHealth
src/totem/screen/adapters/hardware_bus.py
tests/{unit,fixtures,hardware}/hardware_runtime/
```

### Pattern 1: Public contract is data-only and import-safe

**What:** `totem_driver_api` models plugin metadata and logical messages using
JSON-compatible primitives and protocol interfaces.  A manifest names the
factory entry point as a string but catalog code never calls `load()`.

**Use:** Every first- and third-party driver; built-ins must not bypass the
catalog.  The entry-point group is `totem.hardware.drivers`, while the
distribution carries a conventional manifest file discoverable from its
metadata ([VERIFIED: `.planning/notes/python-hardware-runtime-ontology.md`]).

```python
# public, Python 3.9-compatible shape; implementation should validate values
@dataclass(frozen=True)
class DriverManifest:
    plugin_id: str
    plugin_version: str
    driver_api: str
    provides: Tuple[CapabilityDeclaration, ...]
    compatibility: Tuple[MatchRule, ...]
    resources: Tuple[ResourceClaim, ...]
    config_schema: Mapping[str, object]
    factory: str                 # "package.module:provider"
    priority: int = 0
```

### Pattern 2: Resolve completely before any provider import/start

**What:** inventory yields immutable `HardwareFacts`; catalog yields validated
manifests; resolver ranks all candidates; broker checks the resulting plan;
only then does the supervisor create hosts.

**Use:** Every enabled binding at startup, and test fixtures.  A priority is a
deterministic tiebreaker only after positive match specificity; equal automatic
matches remain an error.  Explicit component binding overrides automatic
matching but still validates manifest/API/prerequisites/resource conflicts.

```text
facts -> static rules -> prerequisite diagnostics -> optional isolated probe
      -> ranked MatchResult(s) -> override check -> ambiguity/error check
      -> complete BindingPlan -> ResourceBroker.acquire -> start host
```

**Evidence required in `MatchResult`:** component ID, plugin/driver version,
positive predicates, rejected predicates/prerequisites, specificity tuple,
priority, override source, and final selection/rejection code.  Do not turn
`wlan0`, `/dev/i2c-*`, or SPI presence into a model identity; the current Wi-Fi
wrapper's `wlan0`/`wlan1` map is precisely the type of weak inference being
removed ([VERIFIED: `src/totem/devices/network/network.py`]).

### Pattern 3: Resource claims are declarative before initialization

**What:** a broker normalizes each manifest/config claim into a `ResourceKey`
and issues a lease only after conflict and shared-radio policy checks.

**Use:** GPIO line/chip, SPI bus/device, I2C bus/address, block mount/path,
network PHY/interface, Bluetooth adapter, D-Bus name, Unix/TCP socket,
credential descriptor.  Claims have `exclusive`, `shared-read`, or a named
compatibility group; no provider takes a physical resource before its lease.

For radios, claims and constraints belong to `radio.shared`: Wi-Fi station, AP,
P2P, and Aware expose separate capability services, while Bluetooth discovery,
advertising, GATT, and L2CAP are separate capability services.  Their shared
PHY/interface/adapter constraints are broker policy, not methods on the
current 250-line `NetworkManager` ([VERIFIED: `src/totem/managers/network_manager.py`]).

### Pattern 4: One logical envelope, two hosts

**Logical request:** `{"type":"display.frame.write","id":"...",
"binding":"...",...}`.  **Logical response:** same type plus `.result`,
the same `id`, `ok`, and a stable `error: {code, message, details?}` on
failure.  Typed pushes omit request correlation and are ignored if unknown;
unknown requests with `id` get a correlated structured error.  This combines
the NIP-5D convention with `totemd`'s observable dispatcher behavior
([VERIFIED: `spec/07-conventions.md`], [VERIFIED: `totemd/src/bus.rs`]).

`protocol.py` owns schema validation, correlation and attachment rules.
`ProcessDriverHost` uses the v1 16-byte network-order frame prefix and Unix
sockets.  It must reject lengths before allocation, verify attachment IDs,
coverage and SHA-256 before dispatch, and bind provider identity to the spawned
session—not message payload.  `InProcessDriverHost` invokes through the same
validator/dispatcher; it may eliminate byte copies only after conformance
proves no Python object/codec-only type bypasses that boundary
([VERIFIED: `references/driver-ipc.md`]).

### Pattern 5: Explicit state and host-specific recovery

Use a binding state record with at least:

```text
DISCOVERED -> MATCHED -> BOUND -> STARTING -> READY
                                        \-> DEGRADED
READY/DEGRADED -> STOPPING -> CLOSED
any nonterminal state -> FAILED -> (backoff restart | QUARANTINED)
in-process uncooperative deadline -> CONTAMINATED -> controlled daemon restart
```

Recommended initial policy (configurable and fake-clock testable): startup
deadline 10 s; normal operation uses the request deadline; cancellation grace
500 ms; process terminate grace 2 s then kill; retry delays 1, 2, 4, 8, 16 s;
five failures in a 10-minute window quarantine the binding/provider group.
These are initial safety knobs, **not Pi performance budgets** [ASSUMED].

On isolated failure, invalidate the generation and pending correlations,
terminate then kill if necessary, wait for confirmed child exit and carrier
closure, release that generation's leases, then re-resolve/reacquire/restart.
On an uncooperative in-process deadline, set `CONTAMINATED`, reject all work
for that binding/group, retain its leases, and request controlled daemon
restart.  `Future.cancel()` or `join(timeout)` alone never proves code stopped
([VERIFIED: `references/dual-host-lifecycle.md`]).

### Pattern 6: Canonical bus, adapters at boundaries

The new FastAPI app creates **one** `HardwareRuntime` in lifespan, eagerly
starts its configured plan, then exposes:

- `POST /bus`: one JSON object → one correlated result;
- `GET /bus/events`: loopback-only SSE of typed, lossy pushes; clients
  reconcile via `hardware.status.get`/`hardware.inventory.get` after reconnect;
- legacy routes: request parsing and output translation into the bus; no direct
  manager construction;
- legacy Python manager facade: capability-handle adapter for old method names;
- screen adapter: narrow `FrameSink`, `PowerStatus`, `HardwareHealth` bus
  ports.  It replaces `DeviceManagerDisplay`'s direct `/health` and
  `/display/image` calls while preserving `totem-screen` behavior
  ([VERIFIED: `src/totem/screen/display.py`]).

The Python bus must bind only `127.0.0.1` and `::1` by default, matching the
control plane's security boundary; the existing hardware API unit currently
binds `0.0.0.0:8000`, so preserving its external behavior must be handled as a
documented legacy facade/deployment decision rather than silently broadening
the new bus ([VERIFIED: `spec/07-conventions.md`], [VERIFIED: `deploy/systemd/totem.service`]).

### Anti-patterns to avoid

- **A new registry plus old registries:** this leaves parallel ownership and
  fails HWR-04/API-05.  Built-ins use the new catalog; old registry exports
  delegate only.
- **`EntryPoint.load()` during scan:** imports untrusted third-party module code
  into the daemon before validation, violating SPI-03/ISO-01.
- **Runtime dispatch on `device_type`/model name:** use facts/profiles/manifests
  and capability IDs; a device profile is data, not a class selector.
- **Base64 display frames in canonical bus or IPC:** explicit binary
  attachments are bounded and avoid inflated control messages
  ([VERIFIED: `references/driver-ipc.md`]).
- **One giant NetworkManager facade:** expose capability services and radio
  broker constraints separately; preserve the class only as legacy facade.
- **Releasing leases on a timeout without proven death:** unsafe for GPIO/SPI/
  I2C/radio resources and forbidden for contaminated in-process code.
- **Calling a subprocess a sandbox:** isolation is a crash/resource boundary;
  device-node/D-Bus/identity policy is a separate least-privilege follow-up.

## Concrete Module Boundaries and Migration Order

1. **Create the public API distribution and fixture plugin.** Version the
   driver API and `CapabilityId` majors.  Add a separately packaged fixture
   distribution with entry point + data manifest; catalog it without importing
   it.  This proves SPI-01/02/03/04/05/06 independently of built-ins.
2. **Implement pure data layers.** Add facts/profile models, manifest
   validation, version compatibility, resolver scoring/diagnostics, typed
   runtime configuration and a resource broker.  No FastAPI, manager, or
   concrete driver imports in these modules (HWR-01/03, CMP-01..04, RUN-02).
3. **Implement protocol and conformance first.** Promote framed JSON and
   attachment checks from spike support code into `hosts.protocol`; create
   host-neutral fixture provider, logical transcript tests, and host generation
   routing.  Keep codec ID 2 reserved but unimplemented in deployed config.
4. **Implement supervision and hosts.** Process host is default; in-process is
   explicit.  Add explicit states, restart/quarantine, health, event stream,
   confirmed-exit lease release, contamination, and fault-injection tests
   (ISO-01..07, RUN-01).
5. **Convert built-ins through the catalog path.** Package/wrap display, UPS,
   NFC, storage, Wi-Fi, and Bluetooth providers with data manifests.  Start
   with mocks and display/UPS; split Wi-Fi and Bluetooth capabilities before
   introducing their old `NetworkManager` facade.  Do not retain direct
   `DriverRegistry` as a fallback owner.
6. **Install capability services and canonical bus.** Build one runtime at
   app lifespan, with eager startup/health.  Add `hardware.*` domain messages,
   loopback bus, SSE, capability handles, and screen ports.  Existing REST
   requests become message translators.
7. **Replace legacy internals with facades.** `devices`, `managers`, and
   `api` only map names/models/errors/environment variables to handles and
   results.  Prohibit imports from these packages under `totem.hardware` via a
   static import test.  Retain commands/units/env names but translate their
   values at the boundary (API-04/05, TST-04).
8. **Run local gates, then defer physical gate.** Full mock/unit/API/
   conformance/resolver/fault suite must pass locally.  Generate a Pi benchmark
   runner and public measurement template, but do not run it until explicitly
   allocated hardware is available (TST-03).

## Requirement-to-Implementation Map

<phase_requirements>
## Phase Requirements

| ID | Description | Research support |
|---|---|---|
| HWR-01 | Facts/profiles, not device subclasses | `HardwareFacts`, data-only profiles, resolver; no model switches. |
| HWR-02 | Independently versioned capabilities | `CapabilityId` with major-version compatibility in public API. |
| HWR-03 | No concrete-driver imports in core | Import-free catalog + static dependency test. |
| HWR-04 | One runtime owns hardware state | Eager single `HardwareRuntime`; facades never own devices. |
| SPI-01 | Third-party distribution entry point | Fixture package registers `totem.hardware.drivers`. |
| SPI-02 | Independently versioned public API | Separate `totem_driver_api` package with no daemon types. |
| SPI-03 | Validate before import | Read distribution manifest before `EntryPoint.load`/child exec. |
| SPI-04 | Manifest declarations | Schema includes versions, capabilities, matches, requirements, config, claims, factory. |
| SPI-05 | Reject incompatible majors | Structured catalog diagnostics before plan/start. |
| SPI-06 | No central edits | Installed metadata catalog, provider manifests, generic bus/handles. |
| CMP-01 | Stable hardware evidence | Inventory `HardwareFacts`: buses, IDs, DT/modalias, interfaces, OS/kernel/services. |
| CMP-02 | Ranked evidence | Ordered `MatchResult` with score/specificity/rejections/priority. |
| CMP-03 | Overrides + ambiguity | Override first; equal automatic candidates fail closed. |
| CMP-04 | Data-driven testability | Manifest/profile/resolver fixtures, optional isolated active probes. |
| ISO-01 | Process default/no daemon plugin import | `ProcessDriverHost`, child executable and deferred provider import. |
| ISO-02 | Global/per-plugin in-process selection | Typed config precedence and effective-config health output. |
| ISO-03 | Same logical protocol | One messages/dispatcher/conformance suite for both hosts and bus. |
| ISO-04 | No pickle/executable serialization | Canonical JSON + raw bounded attachment carrier. |
| ISO-05 | Supervision/release after death | Generation, deadline, terminate/kill/wait, retry/quarantine, confirmed lease release. |
| ISO-06 | Cooperative in-process contamination | Cancel/grace/liveness check; retain leases and require daemon restart. |
| ISO-07 | Declared resources/privileges | Manifest claims → brokered handles; document sandbox limitation and plan follow-up policy. |
| RUN-01 | Explicit lifecycle | Binding state machine + event/health snapshots. |
| RUN-02 | Resource broker conflicts | Canonical `ResourceKey`, leases, conflict diagnostics before init. |
| RUN-03 | Radio concurrency explicit | `radio.shared` claim/constraint policy and separate capability services. |
| API-01 | Handles, not models/driver IDs | Capability clients dispatch typed messages to binding handles. |
| API-02 | Separate Wi-Fi/Bluetooth capabilities | Split current `NetworkManager` surface and retain it as facade only. |
| API-03 | Screen narrow ports | `FrameSink`, `PowerStatus`, `HardwareHealth` adapter over bus. |
| API-04 | Preserve legacy interfaces | Translation facades for imports/CLI/routes/env/systemd. |
| API-05 | Canonical never imports facades | Layer rule and static import test. |
| TST-01 | Reusable conformance in both hosts | Fixture provider + shared normalized transcripts, attachment/events/deadlines. |
| TST-02 | Resolver fixture matrix | Exact/override/prereq/ambiguity/conflict/unsupported platform fixtures. |
| TST-03 | Pi-class host benchmark | PSS/startup/latency/frame/recovery harness and deferred acceptance runbook. |
| TST-04 | Preserve/equate current tests | Re-target existing registry, API, mock, radio, screen, hardware tests through facades. |
</phase_requirements>

## Don't Hand-Roll

| Problem | Do not build | Use instead | Why |
|---|---|---|---|
| Python distribution discovery | Custom `sys.path` scanner or central import list | `importlib.metadata` entry points + distribution files | Allows independent installation and metadata inspection without provider import. |
| TOML parsing | Ad-hoc line parser | `tomli` after human package verification | TOML edge cases/security diagnostics should not become runtime code. |
| Logical message format per host | Different Python method and socket protocols | One validated JSON-compatible envelope model | Prevents process/in-process semantic drift. |
| Binary control payload | Base64-in-JSON or line-delimited framing | Tested length-prefixed header + raw attachments | Enforces bounds/checksums/fragmentation correctly. |
| Thread termination | `Future.cancel()`/`join(timeout)` as kill | Cooperative cancellation + contamination | Python cannot safely kill a live arbitrary thread. |
| Resource collision policy | Per-manager mutexes | Central claim broker and leases | Detects cross-driver conflicts before physical initialization. |
| SSE reliability promise | Unbounded event replay queue | Lossy typed SSE plus status reconciliation | Matches the established local bus convention. |

## Runtime State Inventory

| Category | Items found | Action required |
|---|---|---|
| Stored data | No committed database/catalog state for Python drivers was found. Storage drivers use runtime files but are hardware providers, not registry state. | Code edit only; do not migrate stored application data. |
| Live service config | `/etc/totem/totem.env` and a deployed service environment are referenced by units but are not in this checkout; current source reads `TOTEM_*` variables. | Preserve values through legacy env adapters; introduce startup TOML separately; manual deployment migration only after Pi acceptance. |
| OS-registered state | `totem.service` and `totem-screen.service` are systemd identities that users rely on. | Keep names/entry points; update unit implementation/bind policy only as an explicit deployment step. |
| Secrets/env vars | Existing `TOTEM_*` values include driver/device selection and storage paths; no secret value is in tracked source. | Legacy adapter reads non-secret names.  New secret settings are credential/file/FD references; never copy value into manifest/message/log. |
| Build artifacts / installed packages | `/opt/totem` virtualenv and installed package artifacts exist on devices by deployment convention; package split would leave old artifacts until redeploy. | Produce explicit package/install/deploy update and test fixture wheel install; do not assume source-tree imports represent installed distribution metadata. |

## Common Pitfalls

### Import-free means no provider execution

Calling `entry_point.load()` during cataloging defeats SPI-03/ISO-01 even if it
only looks like metadata access.  Locate and validate the manifest from
distribution files first; only the selected process child imports its provider.

### A timeout is not proof of cleanup

In-process plugin code can continue after the caller stops waiting.  Mark
contamination, retain every lease and force controlled restart; starting a
replacement can make GPIO/I2C/radio state unsafe ([VERIFIED:
`references/dual-host-lifecycle.md`]).

### Provider grouping changes the blast radius

Per-provider default reduces interpreter footprint but a provider crash takes
all of its bindings.  Store grouping independently from execution mode and
make health report group membership/generation; never silently imply that a
binding-only crash domain exists ([VERIFIED: `references/process-topology.md`]).

### Keep protocol identity out of payload trust

The supervisor establishes provider and binding identity at spawn/route time.
A child cannot be permitted to impersonate a different provider just by adding
fields to a JSON frame ([VERIFIED: `references/driver-ipc.md`]).

### New bus must not accidentally become public

The established bus is loopback-only.  Keep browser/public projections on the
web/control-plane surfaces and preserve old hardware HTTP behavior only through
an intentional compatibility bind/route decision—not an unrestricted new bus
([VERIFIED: `spec/07-conventions.md`]).

### Screen remains a client boundary

Do not move render state, boot sequence, or direct SPI/GPIO use into the
runtime.  Screen currently owns rendering/readiness/systemd notification and
only submits frames to the device API; keep that direction while making the
port names honest ([VERIFIED: `src/totem/screen/`]).

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | `pytest >=7.3,<9.0`, configured in `pyproject.toml` |
| Test roots | `tests/unit`, `tests/hardware` |
| Markers | `unit`, `mock_transport`, opt-in `hardware` |
| Quick run | `python -m pytest tests/unit -m 'unit and mock_transport' -x` |
| Full local suite | `python -m pytest tests/unit -x` |
| Hardware gate | `python -m pytest tests/hardware --run-hardware` only after explicit allocation |

The current controller lacks a runnable `pytest`/project virtual environment,
so no suite was executed during research.  Creating the project test
environment is Wave 0; it is not evidence that bench hardware is allocated.

### Phase Requirements → Test Map

| Requirements | Behavior | Test type / command | Wave 0 file |
|---|---|---|---|
| HWR-01..04, SPI-01..06 | Fixture distribution metadata, manifest-before-import, dependency direction, one runtime owner | unit: `tests/unit/hardware_runtime/test_catalog.py` | New |
| CMP-01..04 | Facts/profile fixtures, exact/override/prereq/ambiguity/platform diagnostics | unit: `tests/unit/hardware_runtime/test_resolver.py` | New |
| RUN-01..03 | State transitions, broker lease/conflict/radio constraints | unit: `tests/unit/hardware_runtime/test_lifecycle.py tests/unit/hardware_runtime/test_broker.py` | New |
| ISO-03..04 | JSON model, frame fragmentation/pipeline/limits/checksum/version/correlation | unit: `tests/unit/hardware_runtime/test_protocol.py` | New, promote spike vectors |
| ISO-01,05,07 | Process import boundary, ready handshake, child crash/hang/leases/restart/quarantine | unit/mock transport: `tests/unit/hardware_runtime/test_process_host.py` | New |
| ISO-02,06 | Config override precedence; cooperative vs contaminated in-process timeout | unit: `tests/unit/hardware_runtime/test_in_process_host.py` | New |
| API-01..05 | Bus result/SSE, handle dispatch, screen ports, REST/import/env facades, forbidden canonical imports | unit: `tests/unit/test_hardware_bus.py tests/unit/test_legacy_facades.py` | New + migrate `test_service_api.py`, `test_screen.py` |
| TST-01 | Same provider transcript through each host | unit: `tests/unit/hardware_runtime/test_conformance.py` | New |
| TST-02 | Resolver regression matrix | unit: `test_resolver.py` | New |
| TST-03 | Startup/PSS/latency/attachments/crash recovery on Pi classes | opt-in benchmark: `tests/hardware/test_driver_host_bench.py --run-hardware` | New, execution deferred |
| TST-04 | Existing drivers, mocks, API/radio/screen and smoke paths | existing suites plus equivalent facade tests | Migrate deliberately |

### Required fault-injection cases

- child never sends `host.ready`; startup deadline gives `startup_timeout` and
  releases no unconfirmed lease owner;
- malformed prefix/header/attachment, oversize declaration, duplicate IDs,
  checksum mismatch, unknown codec/version, pipelined/fragmented frames;
- unknown unsolicited push ignored; unknown request with `id` returns a stable
  `.result` error;
- isolated child hang/crash: daemon stays alive, confirmed exit precedes lease
  release and next generation; backoff then quarantine;
- in-process cooperative deadline: cancellation observed and later work works;
- in-process uncooperative deadline: live thread → `CONTAMINATED`, new work
  rejected, lease held until controlled daemon restart;
- explicit binding override beats automatic match but cannot bypass incompatible
  API major, invalid config, prerequisite, or resource diagnostics;
- separate Wi-Fi/Bluetooth capability requests exercise shared-radio denial
  and allowed compatibility combinations.

### Pi-class acceptance matrix (deferred, required before cutover)

Run the same pinned driver workload on armv6l, armv7l, and aarch64 only after
explicit allocation.  Record Python/runtime/package versions and each result
in the public contract: provider versus binding grouping, PSS from
`/proc/<pid>/smaps_rollup` (RSS only labeled fallback), startup-to-ready,
steady PSS, p50/p95 control latency, 4,000-byte display-frame transfer,
event load, kill/hang recovery, and leases after death.  No acceptance number
may be inferred from local macOS spike RSS/latency
([VERIFIED: `references/process-topology.md`], [VERIFIED: `01-CONTEXT.md`]).

### Wave 0 gaps

- [ ] Create/install a Python 3.9 project test environment; `pytest` was not
  available on the controller used for this research.
- [ ] Add public driver API fixture distribution and wheel/install fixture.
- [ ] Promote spike protocol/dual-host vectors into production-independent
  unit fixtures without importing spike code as production code.
- [ ] Add fake clock/process/Unix-socket/resource-broker fixtures.
- [ ] Add a static import-layer test (`totem.hardware` may not import legacy
  `totem.api`, `totem.devices`, or `totem.managers`).
- [ ] Add benchmark harness/runbook, but do not schedule bench execution.

## Security Domain

| ASVS category | Applies | Standard control |
|---|---|---|
| V2 Authentication | Limited | New loopback bus inherits local-host boundary; do not expose it publicly. Plugin installation trust is explicitly v2. |
| V3 Session Management | Yes | Spawn-bound host generation and pending request correlation; discard stale-generation results. |
| V4 Access Control | Yes | Resource broker leases and per-host declared descriptor/privilege allowlist; legacy routes do not grant direct hardware ownership. |
| V5 Input Validation | Yes | Validate TOML, manifests, facts, message object, prefix lengths, attachment metadata/checksum, and every bus action before dispatch. |
| V6 Cryptography | Yes | Use stdlib SHA-256 only to verify attachment integrity; do not invent signatures/provenance. Secret references stay out of data models/logs. |

| Threat pattern | STRIDE | Mitigation |
|---|---|---|
| Malicious/buggy package imports during scan | Tampering / elevation | Validate distribution manifest without provider import; default child host. |
| Oversize or malformed IPC frame | DoS | Prefix bounds before allocation/read; exact reads; fixed frame/attachment limits. |
| Stale child result after restart | Tampering | Host generation in pending-route table; discard old generation results. |
| In-process hang with hardware still active | DoS / tampering | Cooperative cancellation, liveness check, contamination, held leases, controlled daemon restart. |
| Two drivers claim same hardware | Tampering / availability | Atomic broker lease acquisition before initialization. |
| Secret appears in diagnostic/event | Information disclosure | Reference/FD only; redact values at config, protocol and logging boundaries. |
| New bus reachable remotely | Elevation / disclosure | Bind canonical `/bus` only to loopback; test bind/route policy. |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `tomli >=2,<3` is the chosen Python 3.9 TOML parser. | Standard Stack | Dependency/package review must choose/approve exact parser before implementation. |
| A2 | Initial retry/quarantine values are 1–16 s, five failures/10 min, 10 s startup, 500 ms cancel grace. | Lifecycle | Values may be unsuitable on Pi; keep config/testable and replace only through measured policy decision. |

## Open Questions

1. **Which exact TOML parser release is approved?**
   - Known: Python 3.9 requires a backport; the local package seam marked
     `tomli` suspicious solely for missing download metadata.
   - Recommendation: verify the official repository/release in the plan's
     package checkpoint, then pin the compatible range.
2. **What service identity/device-node/D-Bus policy will enforce ISO-07?**
   - Known: process isolation is not a full sandbox; the existing units use
     `NoNewPrivileges` but do not define provider-specific device policies.
   - Recommendation: implement declared-resource broker/FD boundaries now and
     record OS sandboxing as a follow-up threat-model acceptance task, not a
     false v1 containment claim.
3. **What Pi budgets select final default grouping/codec?**
   - Known: canonical JSON/per-provider are provisional candidates; local
     measurements are not fleet budgets.
   - Recommendation: keep protocol/grouping config explicit and block deployed
     default change on allocated armv6l/armv7l/aarch64 evidence.

## Sources

### Primary (local, verified)

- [`.planning/phases/HW-01-capability-oriented-hardware-runtime/01-CONTEXT.md`](01-CONTEXT.md) — locked scope, startup/config/cutover decisions.
- [`.planning/notes/python-hardware-runtime-ontology.md`](../../notes/python-hardware-runtime-ontology.md) — proposed ontology, package direction, migration and verification strategy.
- [`.codex/skills/spike-findings-totem/references/driver-ipc.md`](../../../.codex/skills/spike-findings-totem/references/driver-ipc.md) — frame format and protocol constraints.
- [`.codex/skills/spike-findings-totem/references/process-topology.md`](../../../.codex/skills/spike-findings-totem/references/process-topology.md) — group/failure/PSS findings.
- [`.codex/skills/spike-findings-totem/references/dual-host-lifecycle.md`](../../../.codex/skills/spike-findings-totem/references/dual-host-lifecycle.md) — containment asymmetry and lease rules.
- [`spec/07-conventions.md`](../../../spec/07-conventions.md), [`totemd/src/bus.rs`](../../../totemd/src/bus.rs), [`totemd/src/web.rs`](../../../totemd/src/web.rs) — established bus shape and loopback SSE behavior.
- [`src/totem/api/app.py`](../../../src/totem/api/app.py), [`src/totem/devices/registry.py`](../../../src/totem/devices/registry.py), [`src/totem/managers/network_manager.py`](../../../src/totem/managers/network_manager.py), [`src/totem/screen/display.py`](../../../src/totem/screen/display.py) — actual migration seams.

## Metadata

**Confidence breakdown:**

- Standard stack: MEDIUM — stdlib/Pydantic and protocol candidate are verified;
  Python 3.9 TOML dependency needs package approval.
- Architecture: HIGH — locked context, local spike evidence, and current source
  seams agree on a clean one-owner design.
- Pitfalls/failure semantics: HIGH — local spike harness specifically tested
  framed protocol and dual-host failure cases.
- Pi performance and OS privilege isolation: MEDIUM — explicit acceptance work
  remains, with no unallocated hardware contact.

**Research date:** 2026-08-22  
**Valid until:** 2026-09-21 for local-code and protocol findings; refresh exact
dependency approval before installing a new package.
