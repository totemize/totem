---
title: Python hardware runtime ontology and plugin architecture
date: 2026-08-22
context: Architecture exploration prompted by the screen package and expanded to the complete Python device-manager subsystem
status: accepted-for-planning
baseline: 211f890b222c6108dc63c57e6e18fc64ed8d8d97
---

# Python Hardware Runtime Ontology and Plugin Architecture

## Decision

Refactor the complete Python hardware subsystem around versioned capabilities,
data-driven hardware facts, declarative driver manifests, deterministic
compatibility resolution, explicit resource ownership, and supervised driver
hosts. Physical device models are data, not subclasses. Concrete drivers are
plugins, not core dependencies.

Third-party drivers must be independently installable Python distributions.
They run in isolated child processes by default. Operators may explicitly use
the same plugin in process globally or per plugin. Both execution modes share
one transport-neutral, NIP-5D-shaped logical contract and the same conformance
suite.

The `screen` package remains a separate deployable bounded context and consumes
narrow capability ports. It is not itself a hardware driver or manager.

## Why the current hierarchy smells

The PR #22 baseline adds valuable typed radio primitives, but the surrounding
structure still mixes several different taxonomies:

- `devices/` combines contracts, discovery decisions, registries, wrappers,
  backends, and physical product assumptions.
- `managers/` contains one manager per historical device category, while
  `NetworkManager` is growing into a facade for Wi-Fi station/AP/P2P/Aware and
  Bluetooth/BLE/GATT/L2CAP behavior.
- API startup imports and constructs a fixed set of manager factories, so a new
  category requires a central edit.
- Driver registries are static lists and driver construction assumes a
  zero-argument class.
- Hardware detection is repeated inside device wrappers and sometimes infers a
  product from weak evidence such as the presence of a bus.
- The base driver lifecycle infers health from implementation attributes rather
  than exposing a deliberate state machine.
- `screen` correctly reaches hardware through HTTP, but a multi-capability
  client named `DeviceManagerDisplay` obscures the actual display, power, and
  health ports.

These choices work for a bounded set of built-in components. They do not scale
to an open-ended matrix of boards, buses, composite HATs, controllers, kernel
features, operating systems, architectures, and independently released drivers.

## Ontology

| Term | Meaning |
|------|---------|
| `HardwareComponent` | An observed physical or operating-system component with stable facts and topology |
| `HardwareFacts` | Bus, address, IDs, modalias, device-tree strings, interfaces, OS, architecture, kernel, and service evidence |
| `DeviceProfile` | Optional data-only defaults, topology expectations, calibration, and labels for a known model or SKU |
| `CapabilityId` | A versioned behavior contract such as `display.frame-sink@1` or `radio.wifi.p2p@1` |
| `DriverPlugin` | An independently distributed provider of one or more capability implementations |
| `DriverManifest` | Import-free metadata describing compatibility, requirements, resources, configuration, and factory entry point |
| `MatchResult` | A candidate score plus positive evidence and explicit rejection reasons |
| `BindingPlan` | The deterministic selection of plugins for discovered components and capabilities |
| `ResourceClaim` | Exclusive or shared ownership requested for GPIO, SPI, I2C, PHYs, interfaces, adapters, D-Bus names, or sockets |
| `DriverSession` | One live binding hosted either out of process or in process |
| `CapabilityHandle` | The application-facing typed handle for operations and events, independent of the selected driver |
| `HardwareRuntime` | Catalog, inventory, resolver, resource broker, supervisor, bindings, health, and events |

`device type` is descriptive metadata only. It must never be used as a switch
that imports code. A new model normally supplies new facts or a profile and
matches an existing capability driver. A genuinely new behavior introduces a
new versioned capability contract.

## Package hierarchy

The public SPI should be independently distributable so plugins do not depend
on daemon internals:

```text
packages/
  totem-driver-api/
    pyproject.toml
    src/totem_driver_api/
      identifiers.py
      manifest.py
      capabilities/
      messages.py
      lifecycle.py
      errors.py
      resources.py
      conformance/

src/totem/
  hardware/
    catalog/
      metadata.py
      entry_points.py
      validation.py
    discovery/
      inventory.py
      probes.py
      matching.py
      resolver.py
    runtime/
      bindings.py
      resource_broker.py
      supervisor.py
      events.py
    hosts/
      base.py
      process.py
      in_process.py
      protocol.py
    capabilities/
      display/
      power/
      storage/
      nfc/
      radio/
        common/
        wifi/
        bluetooth/
    drivers/
      builtin/
        waveshare/
        pisugar/
        linux_networkmanager/
        linux_bluez/
    api/
      app.py
      inventory.py
      capabilities.py
      health.py
      events.py
      legacy.py

  screen/
    domain/
    application/
    ports/
    adapters/
      hardware_api/

  api/       # legacy import facade
  devices/   # legacy import facade
  managers/  # legacy import facade
```

The dependency direction is strict:

```text
totem-driver-api ← third-party plugins
totem-driver-api ← hardware catalog/discovery/runtime/hosts
hardware runtime ← capability API adapters and legacy facades
capability ports ← screen and other applications
```

The public driver API never imports `totem.hardware`, FastAPI, screen code, a
manager, or a concrete driver. Canonical runtime code never imports through the
legacy `api`, `devices`, or `managers` facades.

## Plugin discovery and manifests

Distributions register through a stable entry-point group:

```toml
[project.entry-points."totem.hardware.drivers"]
waveshare_epd = "totem_driver_waveshare.plugin:provider"
```

Catalog discovery must not call `EntryPoint.load()`. The distribution contains
a conventional manifest file that the catalog locates through installed
distribution metadata and validates before plugin code is imported. A manifest
contains at least:

- stable reverse-DNS plugin and driver IDs;
- plugin, driver-API, and wire-protocol compatibility ranges;
- provided capability IDs and versions;
- static hardware match rules and optional isolated active probes;
- supported OS, architecture, kernel, service, and Python constraints;
- configuration schema and safe defaults;
- exclusive/shared resource claims and required privileges;
- factory entry point and package provenance;
- deterministic priority and match specificity.

Built-in drivers register through the same catalog path. There is no privileged
second registry for first-party implementations.

## Compatibility resolution

```text
inventory facts
  → statically compatible manifests
  → prerequisite filtering
  → isolated active probes where necessary
  → ranked MatchResults with evidence
  → resource-conflict validation
  → deterministic BindingPlan
```

Precedence is explicit operator binding, exact immutable hardware identity,
strong platform evidence, then weaker probes. A tie between equally valid
automatic candidates is an error with diagnostics. The runtime never guesses a
panel or UPS model merely because SPI or I2C exists.

Profiles describe known composite products and calibrations but do not select
classes. Compatibility matrices are derived from manifest constraints and
resolver fixtures instead of being hand-maintained in manager code.

## Dual driver hosts

```text
HardwareRuntime
  └── DriverHost
      ├── ProcessDriverHost    # default
      │     └── versioned IPC → plugin process
      └── InProcessDriverHost  # explicit opt-in
            └── same envelopes → plugin provider
```

The runtime selects the host from a global default and optional per-plugin
override:

```toml
[hardware.plugins]
default_execution = "process"

[hardware.plugins."org.totem.waveshare"]
execution = "in_process"
```

Commands, results, events, health, lifecycle transitions, and errors reuse the
NIP-5D message pattern already adopted by Totem's loopback bus
(`spec/07-conventions.md`, `spec/10-control-plane.md`, and
`totemd/src/bus.rs`):

```json
{ "type": "display.frame.write", "id": "req-42", "frame": { "attachment": "frame-1" } }
{ "type": "display.frame.write.result", "id": "req-42", "ok": true }
{ "type": "display.refresh.completed", "binding": "display-0" }
```

The first `type` segment owns a capability domain, `id` correlates requests and
results, `.result` names a response, and unsolicited typed pushes carry events.
Plugin and binding identity is attested by the carrier/session established at
spawn time rather than accepted from message payloads. Capability availability
is negotiated from the validated driver manifest before the session starts.

NIP-5D defines logical JSON-object semantics over a replaceable carrier. The
driver-host protocol follows the same separation. Spike 002a validated a
framed canonical-JSON representation over a Unix-domain transport; 002b proved
that MessagePack can encode the *same* envelope but did not justify it as the
v1 default. No capability behavior or schema may vary by encoding. The fixed
prefix carries explicit protocol and codec versions, and the decoder rejects
unsupported values before dispatch.

Pickle and executable object serialization are forbidden. Binary data uses a
bounded, explicitly described attachment rather than changing the control
envelope. The attachment table declares IDs, media types, lengths, and hashes;
the carrier bounds header bytes, total payload bytes, and attachment count.
The in-process adapter uses the same schema validation boundary so behavior
does not fork and conformance tests run unchanged against both hosts. It may
avoid an unnecessary physical byte copy only if codec-only types still cannot
enter the logical API.

The current NIP-5D draft silently ignores unrecognized types for forward
compatibility, whereas `totemd` returns a correlated `ok: false` result for an
unknown request. The validated combined rule is: ignore unknown unsolicited
pushes, but return a structured error for an unknown ID-bearing request so the
caller does not wait for a timeout.

Functional parity is not containment parity:

| Concern | Process host (default) | In-process host (opt-in) |
|---------|------------------------|--------------------------|
| Capability envelopes and attachments | Shared contract and conformance suite | Shared contract and conformance suite |
| Cooperative cancellation | Supported | Required for clean recovery |
| Uncooperative timeout | Terminate child, wait for death, release leases, restart | Mark `CONTAMINATED`, reject work, retain leases, restart daemon |
| Native/process-fatal crash | Daemon survives and supervises restart | Daemon exits; service manager performs whole-daemon recovery |
| Trust implication | Plugin code stays outside daemon address space | Operator accepts plugin code in daemon address space |

The host-mode choice must therefore be visible in effective configuration and
health output. Selecting in-process execution is an explicit acceptance of
weaker containment, not merely a latency toggle.

The process supervisor owns startup and operation deadlines, hard termination,
heartbeats, crash detection, bounded restart backoff, quarantine, logging, and
resource release after confirmed process death. Plugin code is imported only
in the child in default mode. In-process deadlines use cooperative cancellation;
the runtime must never release a lease or start a replacement while a timed-out
plugin thread is still alive.
OS-level privilege separation additionally requires distinct identities,
device-node allowlists, D-Bus policy, and other sandboxing; a subprocess alone
is a fault boundary, not a complete security boundary.

Canonical JSON with raw attachments is the provisional v1 carrier. One process
per provider distribution is the provisional scalable grouping; per-binding
grouping remains an override for smaller crash domains. Both choices retain a
Pi-class acceptance gate. Local desktop numbers are evidence about shape and
failure domains, not fleet budgets.

## Lifecycle and resource ownership

Bindings use an explicit state machine:

```text
DISCOVERED → MATCHED → BOUND → STARTING → READY
                                      ↘ DEGRADED
READY/DEGRADED → STOPPING → CLOSED
any state → FAILED → restarting or QUARANTINED
in-process timeout with live code → CONTAMINATED → daemon restart
```

The resource broker resolves claims before startup and issues leases that are
revoked on normal close or confirmed process death. A cooperative in-process
cancellation may close normally; an uncooperative timeout retains its leases
until the daemon exits. Radio coexistence belongs here: Wi-Fi station, AP, P2P,
Aware, Bluetooth scanning, advertising, GATT, and L2CAP are capabilities
coordinated through shared PHY/interface/adapter constraints, not methods
accumulated on one `NetworkManager`.

## API and application boundaries

Hardware APIs expose inventory, bindings, capability operations, health, and
events. Adding a driver for an existing capability creates no new route.
Adding a genuinely new capability adds a versioned schema and capability
adapter, not a device-specific endpoint.

The screen application consumes separate ports such as `FrameSink`,
`PowerStatus`, and `HardwareHealth`. Its HTTP implementation may share a
connection pool, but the domain does not receive a multi-purpose object named
as a display. Rendering and presentation state remain inside `screen`; frame
refresh, hardware locking, and panel lifecycle remain behind the display
capability.

## Compatibility and migration

Migration is incremental rather than a directory-only rewrite:

1. Introduce the public contracts, manifests, catalog, and conformance harness.
2. Wrap every existing built-in driver as a plugin without changing behavior.
3. Add inventory, resolution, resource leases, and explicit lifecycle.
4. Add both driver hosts with isolated execution as the default; use Pi
   performance and recovery gates to lock process grouping and budgets.
5. Split capability services out of the current managers, beginning with the
   radio facade from PR #22.
6. Move API and screen callers onto capability handles.
7. Retain `totem.api`, `totem.devices`, and `totem.managers` as delegating
   compatibility facades; emit deprecation guidance only after replacements are
   stable.
8. Remove a facade only through an explicit versioned compatibility decision.

Throughout migration, keep the `totem`, `totem-api`, and `totem-screen` entry
points, `totem.service` and `totem-screen.service`, deployed environment names,
and existing HTTP routes operational.

## Verification strategy

- Run each driver through capability and lifecycle conformance tests against
  both host modes.
- Exercise resolver fixtures for exact matches, overrides, ambiguity, missing
  prerequisites, unsupported versions, and resource conflicts.
- Kill, hang, and corrupt isolated driver sessions to verify deadlines,
  restart, quarantine, diagnostics, and lease cleanup.
- Run the shared functional suite in both modes, then separately verify that
  in-process hangs contaminate the binding without releasing leases and that
  process-fatal calls cannot be advertised as contained in that mode.
- Benchmark startup, resident memory, control-operation latency, event load, and
  display-frame transfer on armv6l/armv7l and aarch64 representatives.
- Retain existing unit/mock/API tests and explicit hardware gates while legacy
  facades delegate to the new runtime.

## Consequences

This design adds a wire protocol, supervisor, compatibility resolver, and
public versioning obligations. Those costs are deliberate: they move extension
risk away from central factory edits and implicit conventions into explicit,
testable contracts. The result supports an open-ended hardware ecosystem while
keeping failure, compatibility, and maintenance behavior observable.

## Spike findings and remaining gates

1. Framed canonical JSON plus bounded raw attachments passed 25 local protocol
   cases and is the v1 candidate. Native MessagePack made a full 3,813-byte
   display frame only 47 bytes smaller; its Python fallback was slower and its
   fleet installation matrix is worse.
2. Per-provider isolation reduced eight empty hosts to one locally, while its
   injected crash affected all eight bindings rather than one. It is the
   provisional default grouping, with per-binding as an explicit override.
3. Both host modes produced identical functional transcripts. Hard hang/crash
   containment cannot be equal: in-process failure contaminates or terminates
   the daemon; process failure can be terminated and restarted independently.
4. Pi-class PSS, startup, latency, frame-transfer, native dependency, and
   restart measurements remain required on armv6l/armv7l and aarch64.
5. The current systemd/device-permission model still needs a separate spike for
   least-privilege device nodes, D-Bus policy, identities, and sandbox controls.
