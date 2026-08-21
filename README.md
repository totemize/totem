# Totem

Totem is a composable, Nostr-native hardware platform. Mesh networking is
provided by [FIPS](https://fips.network); this repository contains the Python
runtime that detects, initializes, and controls local hardware.

## Device support

- Waveshare 2.13-inch and 3.7-inch E-Ink displays
- ACR122 and PN532 NFC readers
- NVMe and confined filesystem storage
- Onboard and USB Wi-Fi interfaces through NetworkManager
- Explicit in-memory transports for development and CI

Mocks are never selected implicitly. Callers must pass `allow_mock=True`, or
set `TOTEM_ALLOW_MOCK_DRIVERS=1` when running the API.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --editable .
```

Install Raspberry Pi transport dependencies with:

```bash
python -m pip install --editable ".[raspberry-pi]"
```

## Run

```bash
totem --host 0.0.0.0 --port 8000
# equivalent API-only entry point
totem-api
```

Useful environment variables:

- `TOTEM_ALLOW_MOCK_DRIVERS=1`: explicitly permit mock transports.
- `TOTEM_STORAGE_ROOT=/var/lib/totem/storage`: confine filesystem storage.
- `TOTEM_EINK_DRIVER=waveshare_2in13_v4`: select an exact display driver for `DisplayManager`, the API service, and hardware tests.
- `TOTEM_EINK_FULL_REFRESH_EVERY=0`: disable scheduled full-refresh promotion; set a positive value only for panels that require an explicit cadence.
- `TOTEM_SCREEN_ROTATION=0|180`: orient presentation frames for the physical panel mount.
- `TOTEM_SCREEN_LOW_BATTERY_PERCENT=20` and `TOTEM_SCREEN_CRITICAL_BATTERY_PERCENT=8`: select power-scene thresholds.
- `TOTEM_SCREEN_SNAPSHOT_POLL_SECONDS=15`, `TOTEM_SCREEN_RECONNECT_SECONDS=2`, and `TOTEM_SCREEN_COALESCE_SECONDS=2.1`: tune continuous snapshot reconciliation and scene quiet time.
- `TOTEM_SCREEN_SEQUENCE_RATES=scene=seconds,...`, `TOTEM_SCREEN_SCENE_DWELLS=scene=seconds,...`, and `TOTEM_SCREEN_SCENE_PRIORITIES=scene=integer,...`: override per-scene animation and arbitration policy.
- `TOTEM_SCREEN_MAX_PENDING_SCENES=8`: bound coalesced one-shot presentation work.
- `EINK_DISPLAY_TYPE=2in13_v1|2in13_v2|2in13_v3|2in13_v4|3in7`: guide display auto-detection.
- `TOTEM_HARDWARE_COMPONENTS=display,nfc,network,storage`: select hardware tests.

On display-equipped devices, `totem-screen.service` owns presentation state
while the device-manager API retains exclusive ownership of SPI/GPIO. After
boot it reconciles `totemd`, device health, and UPS snapshots continuously;
SSE is only a wake-up notification. Replay the boot state machine with
`totem-screen replay-boot`, or every exact runtime frame with
`totem-screen replay-states --replay-frame-seconds 2`. Add
`--atlas-output /tmp/totem-states.png` to save the same rendered frames as a
contact sheet.

## Test

```bash
python -m pip install --editable .
python -m pip install "pytest>=7.3,<9" "pytest-cov>=4,<7" "httpx>=0.27,<0.28"
pytest -m "unit and not hardware"
```

Physical hardware checks are opt-in:

```bash
pytest tests/hardware -m hardware --run-hardware
```

The source-controlled `metot` hardware profile is
[`deploy/devices/metot.env`](deploy/devices/metot.env). See
[`deploy/README.md`](deploy/README.md) for installation and SPI setup.

## Layout

```text
src/totem/
├── api/           # FastAPI and WebSocket contracts
├── devices/       # Driver contracts, registries, and transports
├── managers/      # Serialized high-level device operations
├── __main__.py    # CLI entry point
└── logging.py     # stdout-first logging
totemd/            # Rust control-plane daemon (spec/10-control-plane.md);
│                  # same binary serves as `totemctl` in client mode
tests/
├── unit/          # deterministic mock-transport tests
└── hardware/      # explicit physical-device smoke tests
docs/hardware/     # wiring and driver notes
deploy/systemd/    # service definitions
```

Display-specific setup is documented in
[`docs/hardware/display.md`](docs/hardware/display.md).
