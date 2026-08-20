---
title: Python device manager
description: FastAPI endpoints, manager lifecycle, driver selection, and library interfaces
---

<!-- generated-by: gsd-doc-writer -->

# Python device manager

The Python service exposes synchronous hardware managers through FastAPI. It
supports E-Ink display, NFC, confined storage, Wi-Fi, Bluetooth/BLE, and UPS
telemetry. The API creates managers lazily, runs their blocking work in
Starlette's thread pool, and serializes operations independently per manager.

This service is separate from the Rust [`totemd` bus](/reference/totemd).
`totemd` is intended to become a client of the hardware API, but that bridge is
not implemented in this revision.

## Run the service

Install the package in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
```

Raspberry Pi transports also need the optional platform dependencies:

```bash
python -m pip install --editable '.[raspberry-pi]'
```

Start the API:

```bash
totem --host 0.0.0.0 --port 8000
```

### CLI options

| Option | Default | Description |
|---|---|---|
| `--host HOST` | `0.0.0.0` | Uvicorn listen address. |
| `--port PORT` | `8000` | Uvicorn listen port. |
| `--log-level LEVEL` | `info` | `debug`, `info`, `warning`, `error`, or `critical`. |
| `--reload` | off | Enable Uvicorn development reload. Do not use for the system service. |
| `--log-file PATH` | stdout | Optional application-log file. |

The `totem-api` entry point starts the same application with its function
defaults. Use `totem` when command-line bind or logging options are needed.

## Service environment

| Variable | Default | Purpose |
|---|---|---|
| `TOTEM_ALLOW_MOCK_DRIVERS` | false | Accepts `1`, `true`, `yes`, or `on` (case-insensitive) to permit explicit mock display, NFC, and network transports. |
| `TOTEM_STORAGE_ROOT` | driver default | Confines storage reads and writes below one directory. The Ansible deployment sets `/var/lib/totem/storage`. |
| `TOTEM_EINK_DRIVER` | empty | Exact display driver selected when `DisplayManager` receives no explicit name. An explicit constructor argument still wins. |
| `TOTEM_UPS_DRIVER` | PiSugar2 fallback | Exact UPS driver selected when `UPSManager` receives no explicit name. Metot is pinned to `pisugar2`; set `waveshare_ups_hat_c` for a Waveshare UPS HAT (C). |
| `TOTEM_I2C_BUS` | `1` | Linux I2C bus used by UPS drivers. |
| `EINK_DISPLAY_TYPE` | empty | Guides display auto-detection: `2in13` or `3in7`. Without it, detected Raspberry Pi displays default to the 3.7-inch driver family. |

Display drivers have additional pin and transport variables documented in
[E-Ink displays](/hardware/display). The production API constructs
`DisplayManager` without an explicit name, so `TOTEM_EINK_DRIVER` is its exact
per-device selection path. Metot's Ansible inventory pins
`waveshare_2in13_v4`.

## HTTP API

The application exposes OpenAPI and Swagger UI using FastAPI's standard paths
(`/openapi.json` and `/docs`).

| Method | Path | Request body | Success response |
|---|---|---|---|
| `GET` | `/` | — | Service name, version, and `status: "running"`. |
| `GET` | `/health` | — | `status: "healthy"` and the names of managers initialized so far. |
| `POST` | `/display/text` | `text`, optional `font_size`, `x`, `y` | `Status` |
| `POST` | `/display/image` | `image_base64` | `Status` |
| `POST` | `/nfc/read` | — | `Status`; read text is embedded in `message`. |
| `POST` | `/nfc/write` | `data` | `Status` |
| `POST` | `/storage/read` | `path` | `StorageReadResponse` with `data_base64`. |
| `POST` | `/storage/write` | `path`, `data_base64` | `Status` |
| `POST` | `/network/configure` | `ssid`, `password`, optional `is_hotspot` | `Status` |
| `GET` | `/network/capabilities` | — | Wi-Fi PHY/concurrency and Bluetooth controller capability matrix. |
| `GET` | `/network/status` | — | Radio blocks, active interfaces, P2P groups, BLE sessions, and advertisements. |
| `GET` | `/ups/status` | — | Model, battery percent, voltage, signed current, and external-power state. |
| WebSocket | `/ws` | client frames are ignored | Typed `DeviceEvent` frames when events are published. |

`Status` has `success: boolean` and `message: string`.

### Display text

```bash
curl --silent http://127.0.0.1:8000/display/text \
  --header 'content-type: application/json' \
  --data '{"text":"hello Totem","font_size":24,"x":10,"y":10}'
```

`font_size` must be greater than zero. The API does not expose the manager's
optional `font_name`; library callers can use that argument directly.

### Display image

The body contains the complete PNG or JPEG file as strict base64—not a data
URL and not a raw framebuffer:

```json
{"image_base64":"iVBORw0KGgo…"}
```

The manager decodes the image with Pillow and converts it through the selected
display driver.

### NFC

Write UTF-8 text:

```bash
curl --silent http://127.0.0.1:8000/nfc/write \
  --header 'content-type: application/json' \
  --data '{"data":"hello"}'
```

`/nfc/read` decodes the driver's bytes as UTF-8 and returns a message such as
`Data read successfully: hello`. There is no structured data field for NFC in
the current response model.

### Storage

Paths must be relative to `TOTEM_STORAGE_ROOT`. Absolute paths, the root
itself, and `..` traversal outside the resolved root are rejected.

```bash
curl --silent http://127.0.0.1:8000/storage/write \
  --header 'content-type: application/json' \
  --data '{"path":"notes/example.bin","data_base64":"aGVsbG8="}'

curl --silent http://127.0.0.1:8000/storage/read \
  --header 'content-type: application/json' \
  --data '{"path":"notes/example.bin"}'
```

API storage writes use the manager defaults: replace the file atomically,
without forced `fsync`, and without changing permissions. The lower-level
Python manager accepts `append`, `atomic`, `sync`, and `permissions` options.

### Network and radio primitives

The network manager exposes hardware mechanisms, observed state, and
capabilities. It does not decide when peers should be discovered, which peer
to join, whether a connection should replace another connection, or what
application protocol should use a formed link. Those choices belong to a
higher-level controller such as `totemd`.

Capability and status responses include:

- physical Wi-Fi PHYs, driver/firmware versions, bands/channels, supported
  interface modes, and the kernel's valid concurrent-interface combinations;
- an operation-by-operation `supported` flag and optional reason;
- Bluetooth controller address/type/name, HCI version/manufacturer/modalias,
  central/peripheral roles, advertisement instance/length limits, and
  supported includes;
- Wi-Fi and Bluetooth soft/hard block state, every active Wi-Fi interface with
  mode/channel/addresses, P2P discovery/groups, and active BLE work.

The complete HTTP surface is:

| Area | Method and path | Primitive |
|---|---|---|
| Inventory | `GET /network/capabilities` | Report hardware and operation support without changing state. |
| State | `GET /network/status` | Report current radios, interfaces, groups, discovery sessions, and advertisements. |
| Wi-Fi radio | `PUT /network/wifi/radio` | Set `enabled` with a bounded `timeout_seconds`. |
| Bluetooth radio | `PUT /network/bluetooth/radio` | Power/unpower and soft-unblock/block the controller. |
| Station scan | `GET /network/wifi/networks` | Return SSID, signal, security, frequency, and channel. |
| Station link | `POST`, `DELETE /network/wifi/connections` | Connect with SSID/password or disconnect the managed station link. |
| Hotspot | `POST`, `DELETE /network/wifi/hotspots` | Create or stop the manager-owned AP connection. |
| P2P discovery | `POST`, `DELETE /network/wifi/p2p/discovery` | Start a bounded NetworkManager find or stop it idempotently. |
| P2P peers | `GET /network/wifi/p2p/peers` | Return peer ID/path/address, signal, last-seen clock, flags, and optional identity fields. |
| P2P groups | `POST`, `GET /network/wifi/p2p/groups`; `DELETE /network/wifi/p2p/groups/{id}` | Create-or-join with a peer, list live state/interface/addresses, or remove it. |
| BLE discovery | `POST`, `DELETE /network/bluetooth/discovery` | Start/stop one independently identified, bounded scan session. |
| BLE observations | `GET /network/bluetooth/devices` | Return address/type/name, UUIDs, base64 data, RSSI/Tx power, timestamps, and connection state. |
| BLE advertising | `POST /network/bluetooth/advertisements`; `DELETE /network/bluetooth/advertisements/{id}` | Register/unregister a caller-defined BlueZ advertisement. |
| BLE connection | `POST /network/bluetooth/devices/{id}/connect` or `/disconnect` | Connect/disconnect a discovered generic device. |
| GATT inventory | `GET /network/bluetooth/devices/{id}/gatt` | Return services and characteristics with UUIDs, flags, values, and notification state. |
| GATT value | `GET`, `PUT /network/bluetooth/devices/{id}/gatt/characteristics/{characteristic_id}` | Read or write strict-base64 characteristic bytes. |
| GATT notification | `POST .../{characteristic_id}/subscriptions`; `DELETE /network/bluetooth/gatt/subscriptions/{id}` | Start or stop a manager-owned notification subscription. |

`POST /network/configure` remains as the compatibility station/hotspot call.
New callers should use the explicit resources above so teardown and timeout
semantics are visible.

Start a bounded Wi-Fi Direct search and inspect peers:

```bash
curl --silent --request POST http://127.0.0.1:8000/network/wifi/p2p/discovery \
  --header 'content-type: application/json' \
  --data '{"duration_seconds":60,"timeout_seconds":15}'
curl --silent http://127.0.0.1:8000/network/wifi/p2p/peers
```

Create-or-join is a mutual opt-in operation. On the tested NetworkManager/PBC
stack, each peer must activate a `wifi-p2p` connection to the reciprocal peer
ID; one-sided activation is allowed to time out without silently disrupting
the infrastructure connection. Poll `GET /network/wifi/p2p/groups` until the
returned state is `active`, then bind application sockets to the reported
interface or address. Remove each side's group ID when finished.

BLE discovery sessions are multiplexed. Stopping one session does not stop
the underlying BlueZ scan while another session remains:

```json
{
  "duration_seconds": 30,
  "service_uuids": ["12345678-1234-5678-1234-56789abcdef0"],
  "duplicate_data": true,
  "session_id": "encounter-probe",
  "timeout_seconds": 15
}
```

Advertisement service/manufacturer data and GATT values use strict base64 at
the HTTP boundary. Passwords, PSKs, PINs, and credentials are recursively
redacted from driver errors and are never included in event data.

Every mutating primitive has an explicit operation timeout. Teardown is
idempotent, and `close()` removes P2P groups, BLE advertisements/connections,
scan sessions, and subscriptions created by that manager instance. Station
and AP links have explicit disconnect/stop primitives rather than implicit
shutdown policy. Cleanup does not disable Wi-Fi, stop FIPS, alter routes, or
tear down unrelated NetworkManager/BlueZ state.

#### Raspberry Pi BlueZ 5.82/kernel 6.18 limitation

On both bench Pis running Raspberry Pi kernel `6.18.34+rpt` and BlueZ 5.82,
BlueZ D-Bus rejects even a minimal `LEAdvertisement1` with controller status
`Invalid Parameters (0x0d)`. Stock `bluetoothctl advertise on` fails the same
way, while a kernel-management test beacon transmits and is discovered by the
device-manager scanner. This matches the Raspberry Pi regression tracked in
[BlueZ issue #2268](https://github.com/bluez/bluez/issues/2268). The driver
does not bypass BlueZ with a privileged management fallback; callers receive
the stable `radio_operation_failed` error until the platform stack is fixed.

### UPS status

`GET /ups/status` lazily opens the configured UPS and returns read-only
telemetry:

```json
{
  "model": "PiSugar 2",
  "battery_percent": 80.0,
  "voltage_volts": 4.0,
  "current_amps": -0.25,
  "power_plugged": false
}
```

Current preserves the IP5209's signed reading. Battery percentage is an
estimate interpolated from PiSugar's published IP5209 voltage curve.
The driver does not change charging, shutdown, or GPIO policy.
Drivers without a direct external-power signal return `null` for
`power_plugged`.

### Error mapping

| Status | Cause |
|---|---|
| `422` | Pydantic validation failure, invalid strict base64, or invalid radio request. |
| `404` | A selected peer, device, characteristic, group, or subscription disappeared. |
| `409` | The live Wi-Fi interface set cannot fit any kernel concurrency combination. |
| `501` | The operation is explicitly unsupported by the detected hardware/backend. |
| `503` | The requested manager could not initialize. The service stays up and other managers remain usable. |
| `504` | A bounded radio/D-Bus operation timed out. |
| `502` | A manager initialized, but the requested hardware or D-Bus operation failed. |

Radio errors use `{"detail":{"code":"…","message":"…"}}`. Stable codes
are `unsupported_feature`, `radio_concurrency_conflict`,
`radio_operation_timeout`, `radio_resource_not_found`,
`invalid_radio_request`, and `radio_operation_failed`.

`/health` reports service lifecycle only. A healthy response does not prove
that unopened hardware exists; use `initialized_managers` and an explicit
operation to establish that manager's readiness.

## Manager lifecycle

At application startup, no hardware manager is created. The lifespan starts
the event processor and allocates two locks per manager type:

- an initialization lock prevents duplicate first-use construction;
- an operation lock serializes that manager's calls.

Display work can therefore proceed concurrently with storage work, while two
display calls are serialized. All manager calls run off the async event loop.
At shutdown, each initialized manager's `close()` method runs before the event
processor is cancelled.

Initialization and operation state live in the process. The service does not
persist a manager registry across restarts.

## Driver selection

Driver names are normalized to lowercase and hyphens become underscores.
Display, NFC, Wi-Fi, and Bluetooth registries accept only allow-listed names
and validate that the imported `Driver` class implements the expected
interface.

Mocks are never an implicit success path. A mock registry entry requires
`allow_mock=True`; the API obtains that setting only from
`TOTEM_ALLOW_MOCK_DRIVERS`.

### Display

| Name | Selection |
|---|---|
| `waveshare_2in13_v1` | Waveshare 2.13-inch V1 controller. |
| `waveshare_2in13` | Compatibility alias for the V2 controller. |
| `waveshare_2in13_v2` | Waveshare 2.13-inch V2 controller. |
| `waveshare_2in13_v3` | Waveshare 2.13-inch V3 controller. |
| `waveshare_2in13_v4` | Waveshare 2.13-inch V4 controller; configured for metot. |
| `waveshare_2in13_pi5` | Raspberry Pi 5 with `EINK_DISPLAY_TYPE=2in13`. |
| `waveshare_2in13_pi5_sw_cs` | Explicit Python selection for Pi 5 software chip select. |
| `waveshare_3in7` | Non-Pi-5 SPI device; default when display type is omitted. |
| `waveshare_3in7_pi5` | Raspberry Pi 5; default when display type is omitted. |
| `mock_eink` | Explicit development/CI transport; requires mock opt-in. |

Auto-detection checks `/proc/cpuinfo` for Raspberry Pi 5 and `/dev/spidev*`
for SPI presence. It cannot identify the attached panel electrically, which is
why `EINK_DISPLAY_TYPE` matters.

### NFC

| Name | Detection |
|---|---|
| `acr122` | USB ID `04e6:5591` from `lsusb`. |
| `pn532` | USB ID `0483:5740` from `lsusb`. |
| `mock_nfc` | Explicit development/CI transport; requires mock opt-in. |

Automatic NFC probing is Linux-only.

### Wi-Fi

| Name | Detection |
|---|---|
| `rpi5_onboard_wifi` | Interface `wlan0`. |
| `usb_wifi_adapter` | Interface `wlan1`. |
| `mock_wifi` | Explicit development/CI transport; requires mock opt-in. |

The real drivers use NetworkManager: `nmcli` for station/AP state and the
persistent system D-Bus client for P2P discovery and group lifecycle. `iw`
provides PHY modes/channels/concurrency, `ethtool` supplies driver/firmware
inventory, and `rfkill` reports block state. Detection is Linux-only and uses
the interface names under `/sys/class/net`.

Bluetooth is composed with the selected Wi-Fi driver. Real hardware uses the
allow-listed `bluez` driver and persistent BlueZ/system-D-Bus ownership;
`mock_wifi` composes the deterministic mock Bluetooth driver for CI parity.

### Storage

| Name | Selection |
|---|---|
| `generic_nvme` | Chosen when `/dev` contains an `nvme*` entry; initialization then requires an `nvme*n1` device. |
| `filesystem` | Fallback when no NVMe entry is detected. |

Both storage drivers use `ConfinedStorage`; the NVMe driver does not bypass
the configured root to expose arbitrary block-device paths.

### UPS

| Name | Selection |
|---|---|
| `pisugar2` | PiSugar 2/IP5209 at I2C address `0x75`; configured for metot. |
| `waveshare_ups_hat_c` | Waveshare UPS HAT (C)/INA219 at I2C address `0x43`; select explicitly with `TOTEM_UPS_DRIVER`. |

Automatic selection requires `/dev/i2c-<TOTEM_I2C_BUS>` to exist;
initialization confirms that the device returns a plausible battery voltage.
Install `smbus2` through the `raspberry-pi` extra or provide the Debian
`python3-smbus` package. The Ansible deployment uses the Debian package.
The Waveshare driver initializes the INA219 with the calibration and sampling
configuration from the [Waveshare UPS HAT (C) reference implementation](https://www.waveshare.com/wiki/UPS_HAT_%28C%29).
These writes affect only the monitor; the driver does not configure the charger
or power path.

## Python manager reference

### `DisplayManager`

```python
DisplayManager(driver_name: str | None = None, *, allow_mock: bool = False)
```

Methods and properties: `width`, `height`, `clear_screen()`,
`display_text(text, font_size=24, x=10, y=10, font_name=None)`,
`display_image_from_file(path)`, `display_image(PIL.Image)`,
`display_bytes(bytes)`, `display_encoded_image(bytes)`, `sleep()`, `wake()`,
and `close()`.

The display manager has an internal re-entrant lock. Share one instance rather
than opening the GPIO/SPI transport independently from multiple callers.

### `NFCManager`

```python
NFCManager(driver_name: str | None = None, *, allow_mock: bool = False)
```

Methods: `read_card() -> str`, `write_card(data: str)`, and `close()`.

### `StorageManager`

```python
StorageManager(driver_name: str | None = None, *, storage_root=None)
```

Methods: `read_data(path) -> bytes`,
`write_data(path, data, options=None) -> bool`, and `close()`.

Write options default to:

```python
{
    "append": False,
    "atomic": True,
    "sync": False,
    "permissions": None,
}
```

### `NetworkManager`

```python
NetworkManager(driver_name: str | None = None, *, allow_mock: bool = False)
```

The compatibility methods remain `scan_networks()`,
`connect_to_network(ssid, password)`, `create_hotspot(ssid, password)`,
`stop_hotspot()`, and `get_wifi_status()`.

The full contract also provides `get_capabilities()`, `get_status()`, both
radio setters/getters, Wi-Fi interface/network inventory, station/AP teardown,
P2P discovery/peer/group lifecycle, BLE discovery/device/advertisement and
connection lifecycle, GATT inventory/read/write/subscription lifecycle,
`set_event_callback()`, and idempotent `close()`.

### `UPSManager`

```python
UPSManager(driver_name: str | None = None)
```

Methods: `get_status() -> UPSStatus` and `close()`. `UPSStatus` contains
`model`, `battery_percent`, `voltage_volts`, `current_amps`, and optional
`power_plugged` fields.

Direct NFC, storage, and network manager calls do not add their own operation
locks. The FastAPI layer supplies serialization; other in-process consumers
must coordinate concurrent access themselves.

## WebSocket event channel

`/ws` accepts a connection and waits for client text frames solely to keep the
connection alive. Published events have this shape:

```json
{
  "device": {"device_type":"display","device_id":"default"},
  "event_type":"state_change",
  "data": {}
}
```

Device types are `display`, `nfc`, `storage`, `network`, and `ups`. In addition
to the generic event types, radio events include Wi-Fi/Bluetooth radio state,
P2P peer found/lost and group formed/removed, BLE device found/expired,
advertisement received, connection changes, and GATT value changes.

The radio drivers publish from D-Bus threads through a thread-safe bridge into
the existing `EventManager` and WebSocket fan-out. These are hardware facts,
not encounter or sync policy, and are distinct from `totemd`'s peer-event SSE
stream.

## Deployment layout

Ansible installs versioned source below `/opt/totem/releases/<git-revision>`,
points `/opt/totem/current` at that release, and keeps the virtual environment
at `/opt/totem/.venv`. The service starts:

```text
/opt/totem/.venv/bin/totem --host 0.0.0.0 --port 8000
```

The role can be excluded with `totem_device_manager_enabled=false`; see the
[Ansible runbook](/operations/ansible). That switch also omits Python-specific
packages and health checks.

Production installs add NetworkManager, BlueZ, `iw`, `rfkill`, `ethtool`,
`iproute2`, Polkit, and `python3-dbus-next`. The service account receives only
the NetworkManager actions required for radio/network primitives and group
access to `/dev/rfkill`; the systemd unit keeps `NoNewPrivileges=true` and
starts after NetworkManager and Bluetooth. No FIPS identity, routing, or
general root privilege is granted.

## Security status

The API enables CORS for all origins with credentials and has no
authentication or authorization dependency. Storage paths are confined, but
display, NFC, and network operations are still physical-control operations.
Do not expose port `8000` outside a trusted boundary without adding access
control.
