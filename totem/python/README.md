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
poetry run test-exact-driver  # Tests the consolidated Waveshare driver

# Storage tests
poetry run nvme-test
poetry run storage-test

# GPIO test
poetry run gpio-test
```

### Testing on Raspberry Pi

When testing on a Raspberry Pi, you can use Poetry just as you would on a development machine:

```bash
# On the Raspberry Pi
cd ~/totem/totem/python
poetry install
poetry run test-exact-driver  # Test the e-ink driver with manufacturer's code

# Run with sudo if needed for hardware access
sudo poetry run test-exact-driver
```

If you need to test from a remote machine, you can SSH into the Pi and run:

```bash
ssh totem@<pi-ip-address> "cd ~/totem/totem/python && poetry run test-exact-driver"
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

## E-Ink Service Management

We've added Poetry scripts to easily manage the E-Ink display service:

### Starting the Service

```bash
# Start the e-ink service (standard mode)
poetry run eink-service

# Start with verbose logging
poetry run eink-service --verbose

# Start in mock mode (no hardware)
poetry run eink-service --mock

# Start with debug logging
poetry run eink-service --debug

# Start with a custom socket path
poetry run eink-service --socket-path=/tmp/custom_eink_socket.sock
```

### Checking Service Status

```bash
# Check the status of the e-ink service
poetry run eink-service-status
```

This will show if the service is running, process information, and socket status.

### Stopping the Service

```bash
# Stop the running e-ink service
poetry run eink-service-stop
```

These commands provide a simple interface to manage the e-ink service without needing to remember complex command-line options or paths.

### Using on Raspberry Pi

When running on a Raspberry Pi, you'll likely need sudo permissions to access the GPIO pins:

```bash
# Start the service with sudo
sudo poetry run eink-service

# Or use the direct command if poetry with sudo has issues
sudo python3 -m scripts.start_eink_service start
```

The service management scripts automatically handle the necessary permissions and cleanups. 