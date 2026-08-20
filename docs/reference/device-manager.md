---
title: Python device manager
description: FastAPI endpoints, manager lifecycle, driver selection, and library interfaces
---

<!-- generated-by: gsd-doc-writer -->

# Python device manager

The Python service exposes synchronous hardware managers through FastAPI. It
supports E-Ink display, NFC, confined storage, and Wi-Fi operations. The API
creates managers lazily, runs their blocking work in Starlette's thread pool,
and serializes operations independently per manager.

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
| `TOTEM_ALLOW_MOCK_DRIVERS` | false | Accepts `1`, `true`, `yes`, or `on` (case-insensitive) to permit explicit mock display, NFC, and Wi-Fi transports. |
| `TOTEM_STORAGE_ROOT` | driver default | Confines storage reads and writes below one directory. The Ansible deployment sets `/var/lib/totem/storage`. |
| `TOTEM_EINK_DRIVER` | empty | Exact display driver selected when `DisplayManager` receives no explicit name. An explicit constructor argument still wins. |
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

### Network configuration

Connect to a station network:

```json
{"ssid":"example","password":"secret","is_hotspot":false}
```

Create a hotspot through the selected driver:

```json
{"ssid":"example","password":"secret","is_hotspot":true}
```

The HTTP API currently exposes neither scan/status nor stop-hotspot methods;
those are available on `NetworkManager` for in-process callers.

### Error mapping

| Status | Cause |
|---|---|
| `422` | Pydantic validation failure or invalid strict base64. |
| `503` | The requested manager could not initialize. The service stays up and other managers remain usable. |
| `502` | A manager initialized, but the requested hardware operation failed. |

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
Display, NFC, and Wi-Fi registries accept only allow-listed names and validate
that the imported `Driver` class implements the expected interface.

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

The real drivers use the `nmcli` executable. Detection is Linux-only and uses
the interface names under `/sys/class/net`.

### Storage

| Name | Selection |
|---|---|
| `generic_nvme` | Chosen when `/dev` contains an `nvme*` entry; initialization then requires an `nvme*n1` device. |
| `filesystem` | Fallback when no NVMe entry is detected. |

Both storage drivers use `ConfinedStorage`; the NVMe driver does not bypass
the configured root to expose arbitrary block-device paths.

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

Methods: `scan_networks()`, `connect_to_network(ssid, password)`,
`create_hotspot(ssid, password)`, `stop_hotspot()`, `get_wifi_status()`, and
`close()`.

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

Device types are `display`, `nfc`, `storage`, and `network`. Event types are
`state_change`, `command_completed`, `error`, `data_available`, and
`hardware_event`.

The `EventManager` supports in-process callback subscriptions and WebSocket
broadcasting, but no built-in route or manager publishes events in this
revision. Do not treat `/ws` as equivalent to `totemd`'s active peer-event SSE
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

## Security status

The API enables CORS for all origins with credentials and has no
authentication or authorization dependency. Storage paths are confined, but
display, NFC, and network operations are still physical-control operations.
Do not expose port `8000` outside a trusted boundary without adding access
control.
