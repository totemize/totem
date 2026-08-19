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
- `TOTEM_EINK_DRIVER=waveshare_3in7_pi5`: select a display in hardware tests.
- `EINK_DISPLAY_TYPE=2in13|3in7`: guide display auto-detection.
- `TOTEM_HARDWARE_COMPONENTS=display,nfc,network,storage`: select hardware tests.

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
