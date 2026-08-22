# Phase 1: Capability-Oriented Hardware Runtime - Pattern Map

**Mapped:** 2026-08-22  
**Scope:** complete Python device-manager subsystem; no hardware was contacted.  
**Rule:** `totem.hardware` and `totem_driver_api` are canonical and must not
import `totem.api`, `totem.devices`, or `totem.managers`. The latter packages
become outward-only facades.

## File Classification

| New/modified area | Role | Data flow | Closest analog | Assignment |
|---|---|---|---|---|
| `packages/totem-driver-api/src/totem_driver_api/{identifiers,manifest,messages,lifecycle,resources}.py` | public model/protocol | transform, request-response | `src/totem/api/models.py` | Partial: retain typed, serializable contracts; do not depend on FastAPI or daemon models. |
| `packages/totem-driver-api/.../capabilities/{display,power,storage,nfc,radio/*}.py` | public capability protocol | request-response, pub-sub | legacy interfaces in `src/totem/devices/{display,ups,nfc,storage,network}/` | Partial: split broad interfaces by capability; keep models/data-only. |
| `src/totem/hardware/catalog/{metadata,manifests,diagnostics}.py` | catalog service | file-I/O, transform | `src/totem/devices/registry.py` | Replace registry: metadata/manifest validation without `import_module` or `EntryPoint.load`. |
| `src/totem/hardware/discovery/{facts,inventory,profiles,resolver}.py` | discovery/resolution service | batch, transform | device wrappers' `_detect_hardware` methods | Partial: turn probes into facts; no default model selection or direct driver loading. |
| `src/totem/hardware/runtime/{config,bindings,broker,lifecycle,supervisor,events}.py` | runtime/service | event-driven, request-response | `src/totem/api/app.py`, `event_manager.py` | Partial: explicit lifespan, locks, and events; ownership moves inward and becomes eager. |
| `src/totem/hardware/hosts/{protocol,unix,process,in_process,worker}.py` | host/transport service | streaming, request-response | spike `references/{driver-ipc,dual-host-lifecycle}.md` | No production analog: promote spike contract, not old direct Python calls. |
| `src/totem/hardware/capabilities/{display,power,storage,nfc,radio/{wifi,bluetooth,shared}}.py` | capability handles | request-response, pub-sub | `NetworkManager`, family wrappers | Partial: narrow delegators over binding handles; Wi-Fi and Bluetooth are distinct. |
| `src/totem/hardware/api/{bus,events,health,legacy_routes,app}.py` | API/controller | request-response, SSE pub-sub | `src/totem/api/app.py`, `event_manager.py`, `totemd/src/bus.rs` | Partial: preserve FastAPI/lifespan/test injection, replace manager routing with envelope dispatch. |
| `src/totem/hardware/builtin/**` plus manifest assets | provider packaging | file-I/O, process launch | current drivers and mocks under `src/totem/devices/**/drivers/` | Partial: retain implementation behavior, expose only through manifests/worker. |
| `src/totem/screen/{ports.py,adapters/hardware_bus.py,display.py}` | bounded-context client/adapter | request-response | `src/totem/screen/display.py` | Strong: preserve readiness retry and async thread boundary; call `/bus`, not legacy REST. |
| `src/totem/{devices,managers,api}/**` | compatibility facade | request-response | current manager/wrapper APIs | Must be changed: translate legacy names/env/routes to canonical handles; never own hardware. |
| `src/totem/__main__.py`, `pyproject.toml`, `deploy/systemd/totem*.service` | entry/config/deployment | startup | `pyproject.toml` scripts | Preserve command and unit names; startup creates exactly one runtime. |
| `tests/unit/hardware_runtime/{test_catalog,test_resolver,test_broker,test_lifecycle,test_protocol,test_process_host,test_in_process_host,test_conformance}.py` | unit/conformance tests | transform, streaming, fault injection | `tests/unit/test_driver_registry.py`, `test_service_api.py` | Partial: retain pytest markers/injected fakes; assert new contract rather than driver modules. |
| `tests/unit/{test_hardware_bus,test_legacy_facades}.py`, migrated API/screen tests | integration/facade tests | request-response, SSE | `tests/unit/test_service_api.py`, `test_screen.py` | Strong: `TestClient`, fake handles, no physical hardware. |
| `tests/hardware/test_driver_host_bench.py` and runbook | opt-in benchmark | batch, process measurement | existing hardware marker convention | No analog: opt-in only, record PSS/latency/recovery; do not contact a Pi. |

## Pattern Assignments

### Public API and canonical models

**Analog:** `src/totem/api/models.py:1-35`.

```python
class DeviceId(BaseModel):
    device_type: DeviceType
    device_id: str = "default"

class Status(BaseModel):
    success: bool
    message: str
```

Keep the project preference for explicit typed request/response models, but
the new public API must use Python-3.9-compatible stdlib data models/protocols
and JSON-compatible values. It must not import `pydantic`, `FastAPI`, manager
classes, or concrete driver types. Capability major compatibility, manifest
schema, resource declarations, attachment descriptors, stable error code, and
lifecycle vocabulary live here.

### Catalog and resolution

**Legacy seam to replace:** `src/totem/devices/registry.py:30-89`.

```python
@dataclass(frozen=True)
class DriverSpec:
    name: str
    module: str
    class_name: str = "Driver"
    is_mock: bool = False

module = importlib.import_module(spec.module)
driver_class = getattr(module, spec.class_name)
```

Retain the useful normalization and structured failure vocabulary, but this is
explicitly *not* an implementation to copy: allow-listed module strings and
`import_module` during lookup violate the new import-free catalog rule. The
new catalog reads an installed distribution's manifest through
`importlib.metadata`/distribution files, validates it, and returns catalog
diagnostics before the selected provider executable imports its factory.

**Legacy fact seams:** `display/display.py`, `ups/ups.py`, `nfc/nfc.py`,
`storage/device.py`, `network/network.py`, and `network/bluetooth.py` each
combine host probing, model inference, registry selection, initialization, and
delegation. Extract only safe evidence collection into inventory:

- display: SPI/device-tree facts plus an explicit panel/profile override;
- power: I2C bus/address facts (never infer a particular HAT from a bus);
- NFC: USB VID/PID facts rather than `lsusb` → driver map;
- storage: device/mount facts and configured filesystem root;
- Wi-Fi: interface/PHY/mode facts; Bluetooth: adapter/D-Bus facts.

Resolver tests must assert exact matching, explicit override, incompatible API
major, absent prerequisite, equal-match ambiguity, and resource conflict.

### Runtime startup, lifecycle, and resources

**Analog:** FastAPI lifespan and serialized synchronous calls in
`src/totem/api/app.py:132-182`.

```python
async with request.app.state.manager_locks[name]:
    manager = request.app.state.managers.get(name)
    if manager is None:
        manager = await run_in_threadpool(factory)

async with request.app.state.operation_locks[manager_name]:
    return await run_in_threadpool(operation, *args, **kwargs)
```

Preserve dependency injection, explicit lifespan start/stop, and keeping
synchronous work off the FastAPI loop. Change the semantic center: construct
one injected `HardwareRuntime` during app lifespan; catalog → resolve → claim
all enabled bindings → start all hosts before readiness is reported. There is
no lazy family manager initialization. Binding health and required-capability
readiness replace `503` based on a manager factory exception.

`runtime/broker.py` has no close analog. It must acquire normalized resource
claims atomically before provider init, associate leases to binding and host
generation, and release only on normal close or confirmed child exit. Model
radio coexistence in `radio.shared`, not as a `NetworkManager` mutex.

### Process and in-process hosts

**Source pattern:** `.codex/skills/spike-findings-totem/references/driver-ipc.md`
and `dual-host-lifecycle.md`.

```python
MAGIC = b"THW1"
PROTOCOL_VERSION = 1
PREFIX = struct.Struct("!4sBBHII")
MAX_HEADER_BYTES = 64 * 1024
MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MAX_ATTACHMENTS = 16
```

The `messages` model is one NIP-5D-shaped logical envelope at both carriers:
`type`, optional request `id`, binding routed by the supervisor, `.result`,
`ok`, structured error, events, and bounded attachment descriptors. The bus
uses HTTP/SSE; `ProcessDriverHost` uses framed Unix streams. Unknown pushes are
ignored; unknown ID-bearing requests receive correlated `unknown_type`.

The host implementation must copy the spike's ordering, not the old wrappers'
direct method calls: version/size validation before allocation, exact stream
read/write, session-bound provider identity, ready handshake, generation-bound
pending routes, terminate → kill → confirmed wait → release leases → restart.
`InProcessDriverHost` uses the same validation/conformance harness but on an
uncooperative timeout marks the binding `CONTAMINATED`, rejects work, and
retains leases until controlled daemon restart.

### Canonical bus, event delivery, and legacy REST translators

**Analog:** `src/totem/api/event_manager.py:32-93`.

```python
if self.processor_task is None or self.processor_task.done():
    self.processor_task = asyncio.create_task(self._process_events())
...
for websocket in self.active_connections:
    try:
        await websocket.send_text(event_json)
    except Exception:
        dead_connections.add(websocket)
```

Retain explicit lifecycle and dropped/dead-client behavior, but replace the
unbounded internal queue/WebSocket-specific protocol with the established
lossy SSE projection of typed canonical events. `/bus` is loopback-only,
receives/returns one logical JSON envelope; `/bus/events` is an SSE projection
and clients reconcile status after reconnect. Do not add a new public REST
surface.

**Legacy seam:** fixed manager creation in `src/totem/api/app.py:95-129` and
per-route `run_in_threadpool` dispatch. `totem.hardware.api.legacy_routes`
translates each existing REST route to the corresponding bus envelope, maps
stable error codes to legacy HTTP responses, and preserves base64 only at the
legacy route boundary. It must not create managers or touch drivers.

### Capability split and boundary facades

**Display/power/NFC/storage facades:** `DisplayManager`, `UPSManager`,
`NFCManager`, `StorageManager`, and the family wrappers become thin adapters
over capability handles. Preserve public names, return shapes, arguments,
environment names such as `TOTEM_EINK_DRIVER`, `TOTEM_UPS_DRIVER`,
`TOTEM_STORAGE_ROOT`, and mock permissions as legacy input translation. They
must contain no driver selection, probing, resource lease, or direct `close`
ownership.

**Network facade:** `src/totem/managers/network_manager.py:11-255` is the
clearest anti-pattern: one constructor claims Wi-Fi and Bluetooth together
(lines 19-28) and one class delegates station/AP, P2P, NAN, radio, BLE scan,
advertising, GATT, and L2CAP. Split the canonical ports at least into Wi-Fi
station/AP, Wi-Fi P2P, Wi-Fi Aware/data path, Bluetooth radio/discovery,
advertising, GATT, and L2CAP, with `radio.shared` enforcing PHY/interface/
adapter constraints. `NetworkManager` remains only a backward-compatible
method-to-handle translator aggregating snapshots for `get_status()`.

Current first-party driver modules—including Waveshare display variants,
PiSugar/Waveshare UPS, PN532/ACR122 NFC, filesystem/NVMe storage,
NetworkManager Wi-Fi/P2P/Aware, and BlueZ/BLE/GATT/L2CAP—become built-in
providers with manifest metadata through the same catalog route as external
plugins. Their mocks become fixture/built-in test providers, not special
registry entries.

### Screen ports

**Analog:** `src/totem/screen/display.py:13-67`.

```python
async def wait_ready(self, timeout: float = 60.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not await self.ready():
        if loop.time() >= deadline:
            raise TimeoutError(...)
        await asyncio.sleep(0.25)
```

Keep screen's async readiness/retry behavior and its ownership of rendering,
boot sequencing, rotation, and systemd notification. Replace the generic
`DeviceManagerDisplay._request('/health'|'/display/image')` client with narrow
`FrameSink`, `PowerStatus`, and `HardwareHealth` ports backed by the canonical
loopback bus. A display frame is a bounded attachment; no direct SPI/GPIO and
no legacy manager import enters `screen`.

### Tests and packaging

**Analog:** deterministic pytest injection in `tests/unit/test_service_api.py:15-82`.

```python
app = create_app({name: lambda value=value: value for name, value in managers.items()})
return TestClient(app), managers
```

Keep `pytest.mark.unit` and `pytest.mark.mock_transport`, `TestClient`, fakes,
and assertions on observable responses. Replace fake managers with fake
catalog/inventory/clock/broker/host/capability-handle fixtures. Promote the
spike's framing, fragmentation, attachment, timeout, crash, restart, and
contamination transcripts into the host conformance suite.

`tests/unit/test_driver_registry.py:15-104` is the migration-equivalence
analog: retain its explicit mock/unsupported-hardware expectations as facade
tests, while new catalog tests assert no provider import at scan time. Add a
static import-layer test that fails if `totem.hardware` imports any legacy
package. Keep hardware tests under the existing opt-in marker only; benchmark
code may be added but must not connect to a bench device.

**Packaging analog:** `pyproject.toml:7-31` preserves Python `>=3.9,<4.0`,
the `totem`/`totem-api`/`totem-screen` script names, and architecture-specific
optional dependencies. Add the separate driver API distribution and fixture
plugin packaging without changing those compatibility commands. The proposed
`tomli` dependency remains a human-verified package gate before modification.

## Shared Patterns

### Boundary direction

```text
screen / legacy API / legacy devices+managers
                     ↓
                 totem.hardware
                     ↓
              totem_driver_api
                     ↑
              provider distributions
```

Only outer packages may import inward. The runtime imports no facade and never
delegates hardware ownership to legacy code. Exactly one runtime is built at
startup.

### Error and diagnostic policy

Follow existing explicit exception/HTTP mapping (`app.py:141-182`) but make
canonical errors stable structured envelopes. Catalog/config/resolution errors
degrade the affected binding with evidence; required binding failure controls
readiness. Redact secrets; pass only references/inherited descriptors.

### Data and binary boundaries

Legacy HTTP base64 is compatibility-only. Canonical bus and driver IPC share
strict JSON values plus bounded raw attachments with media type, length, and
SHA-256. Never use pickle, implicit arbitrary Python objects, or one `recv()`
as a frame boundary.

## Mandatory Facade Inventory

| Legacy area | New inward target | Facade may retain | Facade must lose |
|---|---|---|---|
| `devices/registry.py` and family `*_DRIVERS` | catalog + resolver | error/name compatibility | static allow-list and provider import |
| display/UPS/NFC/storage wrappers and managers | corresponding capability handles | methods/env aliases/return shapes | detect/load/init/close ownership |
| `NetworkManager` | Wi-Fi/Bluetooth handles + radio broker | legacy aggregated methods/status | joint radio ownership and policy |
| `api/app.py` REST routes | `hardware.api.bus` | route paths/HTTP shapes | fixed manager factory map/lazy ownership |
| `screen/display.py` | narrow bus ports | retry/timeouts/frame conversion | `/health` and `/display/image` coupling |

## No Analog Found

| File/area | Reason |
|---|---|
| distribution-manifest inspection without provider import | current registry imports at lookup; follow research/stdlib metadata pattern |
| deterministic compatibility resolver and resource lease broker | present code selects a driver per family but has no cross-capability plan/conflict model |
| framed Unix driver carrier and process supervisor | no current process driver boundary; use spike vectors |
| contaminated in-process lifecycle and generation routing | current drivers expose inferred lifecycle only |
| Pi PSS benchmark/runbook | hardware tests exist but do not establish the required process metrics |

## Metadata

**Analog search scope:** `src/totem/{api,devices,managers,screen}`, `tests/unit`,
`pyproject.toml`, spike references, and existing `totemd` bus convention.  
**Files analyzed:** representative contracts, registry, all manager families,
family wrappers, API/event models, screen client, unit tests, and packaging.  
**Physical-device activity:** none; Pi acceptance remains explicitly deferred.
