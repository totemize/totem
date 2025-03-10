# Totem Python Software

This repository contains the Python software for the Totem project, which interfaces with various hardware components like e-Paper displays, NFC readers, NVMe storage, and WiFi controllers.

## Setup

### Prerequisites

- Python 3.9 or newer
- Required Python packages (installed automatically with Poetry or pip)

### Installation

#### Using Poetry (Recommended)

```bash
# Install Poetry
# macOS / Linux / WSL
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

#### Using pip and venv

```bash
# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On Linux/macOS
source venv/bin/activate
# On Windows
venv\Scripts\activate

# Install dependencies
pip install pillow numpy
```

## System Test

The project includes a comprehensive system test that checks all hardware components:

- E-Ink Display
- NFC Reader
- NVMe Storage
- WiFi Controller

### Running System Test

```bash
# Using Poetry
poetry run python system_test.py

# Or using venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
python system_test.py
```

### Auto Test Mode

When running on non-Linux platforms (like macOS or Windows) or when the `AUTO_TEST` environment variable is set, the system test will run in auto mode, which:

- Uses mock implementations for hardware that isn't available
- Automatically proceeds through user prompts
- Reports successful tests even when hardware is not present

This makes it easy to run tests in development environments without real hardware.

To explicitly enable auto test mode:

```bash
# On Linux/macOS
AUTO_TEST=1 python system_test.py

# On Windows PowerShell
$env:AUTO_TEST=1; python system_test.py
```

## Device Drivers

The system supports various hardware devices, with modular drivers for each component:

- **E-Ink Display**: Supports Waveshare 3.7-inch e-Paper HAT
- **NFC Reader**: Supports multiple NFC readers including ACR122 and PN532
- **Storage**: Supports NVMe storage and fallback to filesystem
- **WiFi**: Supports built-in WiFi and USB WiFi adapters

Each driver is designed to automatically detect available hardware and fall back to mock implementations for testing.

## Project Structure

```
python/
├── devices/             # Hardware device drivers
│   ├── eink/           # E-Ink display
│   ├── nfc/            # NFC reader
│   ├── nvme/           # NVMe storage
│   └── wifi/           # WiFi controller
├── managers/           # High-level managers for devices
├── utils/              # Utility functions and helpers
├── logs/               # Log files
├── system_test.py      # System test
└── totem-python.service # Systemd service config
``` 