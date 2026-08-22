# Requirements: Totem Hardware Runtime

**Defined:** 2026-08-22
**Core Value:** Maintainers can add independently packaged hardware drivers
without editing Totem core or destabilizing existing capabilities.

## v1 Requirements

### Ontology and dependency boundaries

- [ ] **HWR-01**: The runtime represents a physical component using observed
  hardware facts and optional data-only device profiles, not a subclass chosen
  from a closed device-type hierarchy.
- [ ] **HWR-02**: Drivers provide one or more independently versioned capability
  contracts such as display output, battery telemetry, Wi-Fi P2P, or BLE GATT.
- [ ] **HWR-03**: Core discovery, resolution, lifecycle, and API modules contain
  no imports of concrete vendor drivers.
- [ ] **HWR-04**: A single hardware runtime owns the plugin catalog, binding
  plan, resource leases, lifecycle state, health, and events.

### Public plugin SPI

- [ ] **SPI-01**: A third party can ship a driver as an independent Python
  distribution and register it through the `totem.hardware.drivers` entry-point
  group without changing Totem source.
- [ ] **SPI-02**: The public driver API is independently versioned and does not
  expose daemon-internal manager or API implementation types.
- [ ] **SPI-03**: The runtime can read and validate a plugin manifest before it
  imports or initializes plugin code.
- [ ] **SPI-04**: Manifests declare driver/API versions, provided capability
  versions, compatibility rules, dependencies, configuration schema, resource
  claims, and factory entry point.
- [ ] **SPI-05**: Incompatible driver API or capability major versions are
  rejected with structured, actionable diagnostics.
- [ ] **SPI-06**: Installing or removing a compatible plugin requires no edit
  to a central registry, manager factory, API router, or device-type switch.

### Compatibility resolution

- [ ] **CMP-01**: Discovery records stable hardware evidence such as bus,
  address, vendor/product IDs, device-tree compatible strings, modaliases,
  interfaces, architecture, OS, kernel, and required services.
- [ ] **CMP-02**: Resolution produces ranked candidates with match evidence,
  rejected prerequisites, specificity, and deterministic priority.
- [ ] **CMP-03**: An explicit operator binding override wins over automatic
  detection, while equally valid automatic matches fail closed rather than
  selecting an arbitrary driver.
- [ ] **CMP-04**: Compatibility decisions and known composite device profiles
  are data-driven and testable without connected hardware.

### Driver execution and supervision

- [ ] **ISO-01**: Drivers execute in a supervised child process by default, and
  default mode does not import third-party driver code into the daemon process.
- [ ] **ISO-02**: An operator can select in-process execution globally or for a
  specific plugin through configuration.
- [ ] **ISO-03**: Isolated and in-process hosts expose identical versioned,
  serializable command, result, event, lifecycle, and error envelopes.
- [ ] **ISO-04**: Driver IPC never uses pickle or another executable object
  serialization format.
- [ ] **ISO-05**: The supervisor enforces startup and operation deadlines,
  cancellation, crash detection, bounded restart backoff, quarantine, and
  deterministic resource release.
- [ ] **ISO-06**: Isolated hosts receive only declared resources and privileges;
  runtime process isolation is documented separately from package trust.

### Lifecycle and resources

- [ ] **RUN-01**: Every binding exposes explicit lifecycle states from discovery
  through binding, startup, readiness/degradation, shutdown, failure, and close.
- [ ] **RUN-02**: A resource broker detects conflicts across GPIO, SPI, I2C,
  network PHYs/interfaces, Bluetooth adapters, D-Bus services, sockets, and
  other exclusive resources before driver initialization.
- [ ] **RUN-03**: Shared-radio concurrency constraints are modeled explicitly
  rather than hidden inside a monolithic network manager.

### Capability-facing applications and compatibility

- [ ] **API-01**: HTTP APIs and local applications consume capability handles
  without knowing physical device models or concrete driver IDs.
- [ ] **API-02**: Wi-Fi station/AP/P2P/Aware and Bluetooth discovery,
  advertising, GATT, and L2CAP are separate capability services coordinated by
  shared radio resources.
- [ ] **API-03**: The screen application depends on narrow display, power, and
  health ports rather than a multi-purpose object named as a display manager.
- [ ] **API-04**: Existing Python import paths, CLI commands, HTTP routes,
  environment variables, and systemd units continue to work through explicit
  compatibility facades during migration.
- [ ] **API-05**: Canonical new code never imports through a legacy facade.

### Verification and maintainability

- [ ] **TST-01**: A reusable conformance suite verifies every driver against
  its declared capability and lifecycle contracts in both execution modes.
- [ ] **TST-02**: Resolver fixtures cover exact matches, missing prerequisites,
  override precedence, ambiguity, resource conflicts, and unsupported platform
  combinations.
- [ ] **TST-03**: The isolated host is benchmarked on Pi-class hardware for
  startup time, steady memory, command latency, binary-frame transfer, crash
  recovery, and process-granularity tradeoffs.
- [ ] **TST-04**: Existing unit, mock-transport, API, and opt-in hardware tests
  remain valid or gain equivalent coverage before a legacy path is retired.

## v2 Requirements

### Ecosystem hardening

- **ECO-01**: Plugin packages can carry independently verifiable signatures and
  provenance metadata.
- **ECO-02**: Driver hosts may support non-Python implementations through the
  same wire contract.
- **ECO-03**: Administrators can manage plugin installation and upgrades through
  an authenticated control-plane workflow.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Product engagement or sync policy inside drivers | Drivers remain policy-free hardware primitives |
| Automatic trust of packages from public indexes | Installation is an explicit administrator trust decision |
| Immediate removal of legacy modules or routes | Compatibility facades are required for incremental migration |
| Rewriting `totemd` | The Rust control plane is a consumer/integration boundary, not this refactor's target |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HWR-01..04 | Phase 1 | Pending |
| SPI-01..06 | Phase 1 | Pending |
| CMP-01..04 | Phase 1 | Pending |
| ISO-01..06 | Phase 1 | Pending |
| RUN-01..03 | Phase 1 | Pending |
| API-01..05 | Phase 1 | Pending |
| TST-01..04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-22*
*Last updated: 2026-08-22 after hardware ontology exploration*
