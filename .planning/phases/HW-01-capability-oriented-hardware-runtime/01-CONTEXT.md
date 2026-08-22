# Phase 1: Capability-Oriented Hardware Runtime - Context

**Gathered:** 2026-08-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the PR #22 Python hardware-manager internals with the accepted
capability-oriented runtime: independently versioned driver contracts,
import-free plugin cataloging, deterministic fact-based resolution, explicit
resource leases and lifecycle, supervised process and opt-in in-process hosts,
and one NIP-5D-shaped application bus. Preserve deployed imports, commands,
routes, environment names, and units only as compatibility facades. Cover
display, power, storage, NFC, Wi-Fi, Bluetooth, and future capability types.

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/totem/devices/contracts.py` supplies the current shared driver lifecycle
  vocabulary; its concrete-attribute inference should be replaced by explicit
  binding state while its compatibility types can be adapted.
- `src/totem/devices/registry.py` centralizes allow-listed import behavior and
  its stable errors; it is the direct seam to replace with distribution
  metadata, import-free manifests, and structured catalog diagnostics.
- PR #22's display, UPS, NFC, storage, NetworkManager, BlueZ, Wi-Fi P2P/Aware,
  BLE/GATT/L2CAP implementations and mock transports are the built-in provider
  behavior that must survive the clean internal cutover.
- The verified spike sources under `.planning/spikes/` provide framed JSON,
  process grouping, failure injection, dual-host behavior, and conformance
  fixtures suitable for promotion into production modules and tests.

### Established Patterns
- The repository supports Python 3.9 and uses typed models, explicit mock
  transports, deterministic unit tests, FastAPI loopback services, environment
  compatibility settings, and systemd-managed processes.
- `totemd` already exposes the project-standard NIP-5D-shaped request/result
  bus with lossy SSE pushes and state reconciliation after reconnect.
- Hardware tests are explicitly opt-in; local test runs must not infer bench
  allocation.

### Integration Points
- `src/totem/api/app.py` currently constructs a fixed manager map and owns the
  deployed REST/WebSocket surface; it becomes the NIP-5D bus host plus legacy
  route translators.
- `src/totem/screen/display.py` currently calls `/health` and `/display/image`;
  its adapter must move to narrow display, power, and hardware-health bus ports
  while retaining `totem-screen` behavior.
- `src/totem/managers/` and `src/totem/devices/` retain import compatibility
  but delegate inward to `totem.hardware`; they are never dependencies of the
  canonical runtime.
- `pyproject.toml`, deployment units, and tests must retain the current
  `totem`, `totem-api`, and `totem-screen` commands and Python 3.9 floor while
  adding the independently distributable public driver API and fixture plugin.

</code_context>

<specifics>
## Specific Ideas

- The change is a clean internal ontology break, not a gradual hybrid of old
  managers and new runtime objects.
- The NIP-5D-shaped message bus is the canonical application API. REST resource
  endpoints are compatibility translations, not a parallel new surface.
- Both host modes share the logical contract and conformance suite, but never
  claim equal containment. A live timed-out in-process call contaminates its
  binding and retains leases until daemon restart.
- Do not contact `totem`, `metot`, or `motown` for acceptance until the user
  explicitly allocates the relevant bench devices.

</specifics>

<deferred>
## Deferred Ideas

- Plugin signatures/provenance, non-Python providers, and authenticated plugin
  installation remain v2 ecosystem work.
- Pi-class acceptance is required before deployment cutover, but physical
  execution waits for explicit bench allocation rather than being inferred
  from autonomous mode.

</deferred>
