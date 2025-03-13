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

## Running Tests

All test scripts have been moved to the `tests` directory and registered as Poetry scripts for easy execution.

### Available Test Scripts

```bash
# System test (checks all hardware components)
poetry run system-test

# E-Ink display tests
poetry run eink-debug
poetry run eink-pattern
poetry run eink-quick-test
poetry run eink-diag
poetry run pi5-eink-test

# Storage tests
poetry run nvme-test
poetry run storage-test

# GPIO test
poetry run gpio-test
```

### Test Options

Most tests support command line arguments:

```bash
# Run system test for a specific component
poetry run system-test --test eink
poetry run system-test --test nvme
poetry run system-test --test wifi
poetry run system-test --test nfc

# Run with debug logging
poetry run system-test --log-level debug
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
AUTO_TEST=1 poetry run system-test

# On Windows PowerShell
$env:AUTO_TEST=1; poetry run system-test
```

## Device Drivers

The system supports various hardware devices, with modular drivers for each component:

- **E-Ink Display**: Supports Waveshare 3.7-inch e-Paper HAT
- **NFC Reader**: Supports multiple NFC readers including ACR122 and PN532
- **Storage**: Supports NVMe storage and fallback to filesystem
- **WiFi**: Supports built-in WiFi and USB WiFi adapters

Each driver is designed to automatically detect available hardware and fall back to mock implementations for testing.

### E-Ink Display Driver

We've integrated the Waveshare e-Paper display driver as a Poetry package to avoid hardcoded dependencies. This approach offers:

- **Proper Package Management**: The driver is managed through Poetry
- **Fallback Mechanism**: The system first tries to use a system-installed driver, then falls back to our local package
- **Portability**: The package works on all platforms including Raspberry Pi 5
- **Easy Updates**: To update the driver, simply replace the files in `devices/eink/waveshare_epd/` with newer versions

See `devices/eink/README_DRIVER.md` for detailed information on the driver integration.

## Project Structure

```
python/
├── devices/             # Hardware device drivers
│   ├── eink/           # E-Ink display
│   │   ├── drivers/    # Driver implementations
│   │   └── waveshare_epd/ # Waveshare driver package
│   ├── nfc/            # NFC reader
│   ├── nvme/           # NVMe storage
│   └── wifi/           # WiFi controller
├── managers/           # High-level managers for devices
├── service/            # Web service components
├── src/                # Core application code
├── tests/              # Test scripts for all components
├── utils/              # Utility functions and helpers
├── logs/               # Log files
├── scripts/            # Utility scripts
├── examples/           # Example code
└── totem-python.service # Systemd service config
``` 

## Running the Service

To start the web service:

```bash
poetry run serve
``` 