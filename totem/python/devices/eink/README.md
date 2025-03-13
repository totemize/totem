# E-Ink Display System

This document explains the architecture of the e-ink display system and how to use it in your applications.

## Architecture Overview

The e-ink display system consists of several components:

1. **EInk Service** - A persistent daemon process that maintains exclusive access to the GPIO pins used by the e-ink display.
2. **EInk Client** - A client library used to communicate with the EInk Service.
3. **DisplayManager** - A high-level manager class that can either use the EInk Client or direct hardware access.

This architecture solves several issues:

- **Resource Contention**: By having a single process maintain exclusive access to the GPIO pins, we avoid "pin is busy" errors.
- **Performance**: The persistent service reduces the overhead of repeatedly initializing and tearing down GPIO connections.
- **Reliability**: Better error handling and recovery mechanisms.

## Usage

### Basic Usage with DisplayManager

The simplest way to use the e-ink display is through the `DisplayManager` class, which works with both the service-based and direct hardware access modes:

```python
from managers.display_manager import DisplayManager

# Create the display manager
dm = DisplayManager()

# Clear the screen
dm.clear_screen()

# Display text
dm.display_text("Hello, World!", font_size=24)

# Display an image from a file
dm.display_image_from_file("/path/to/image.png")

# Put the display to sleep
dm.sleep()

# Wake the display
dm.wake()
```

### Using the EInk Service

The EInk Service maintains persistent access to the display hardware. Here's how to use it:

#### Starting the Service

Start the service using the provided script:

```bash
# Start the service with auto-detected driver
python3 -m scripts.start_eink_service start

# Start with a specific driver
python3 -m scripts.start_eink_service start --driver waveshare_3in7
```

#### Installing as System Service

For production use, you can install the service to start automatically at boot:

```bash
# Install the service
sudo python3 -m scripts.install_eink_service install --driver waveshare_3in7

# Check service status
systemctl status eink.service

# Uninstall the service
sudo python3 -m scripts.install_eink_service uninstall
```

#### Connecting to the Service

To use the service in your application, set the `USE_EINK_SERVICE` environment variable to `1`:

```bash
# Run your application with the service
USE_EINK_SERVICE=1 python3 your_application.py
```

Or set it in your Python code:

```python
import os
os.environ['USE_EINK_SERVICE'] = '1'

from managers.display_manager import DisplayManager
# ... rest of your code
```

### Direct Client Usage

If you want more control, you can use the EInk Client directly:

```python
from devices.eink.eink_client import EInkClient

# Create a client
client = EInkClient()

# Send commands
client.clear_display()
client.display_text("Hello from Client", font_size=36)
client.sleep_display()
```

### Command-line Usage

You can also control the display from the command line:

```bash
# Display text
python3 -m devices.eink.eink_client text "Hello, World!" --font-size 24

# Display an image
python3 -m devices.eink.eink_client image /path/to/image.png

# Clear the display
python3 -m devices.eink.eink_client clear
```

## Testing

Run the system test to verify your display is working:

```bash
# Run the test with direct hardware access (default)
python3 -m tests.system_test

# Run the test with the service
python3 -m tests.system_test --use-service
```

## Environment Variables

The e-ink display system uses several environment variables:

- `USE_EINK_SERVICE`: Set to `1` to use the service, `0` for direct hardware access (default: `0`)
- `EINK_DISPLAY_TYPE`: Specifies the driver to use (e.g., `waveshare_3in7`)
- `EINK_TEST_MODE`: Set to `1` to force direct hardware access for testing
- `EINK_USE_TCP`: Set to `1` to use TCP instead of Unix sockets for service communication
- `EINK_SOCKET_PATH`: Custom path for the Unix socket (default: `/tmp/eink_service.sock`)
- `EINK_TCP_HOST`: TCP host address (default: `127.0.0.1`)
- `EINK_TCP_PORT`: TCP port (default: `9500`)

## Troubleshooting

### Service Won't Start

Check the service logs:

```bash
cat /tmp/eink_service.log
```

### Permission Issues

Make sure your user has access to GPIO devices:

```bash
sudo usermod -a -G gpio your_username
```

### Socket File Issues

If the socket file becomes stale, you can remove it:

```bash
rm /tmp/eink_service.sock
```

Then restart the service.

## Extending the System

### Adding New Drivers

To add a new driver for a different e-ink display:

1. Create a new driver in the `devices/eink/drivers` directory
2. The driver should follow the same interface as the existing drivers
3. Use the driver by specifying its name, e.g., `DisplayManager(driver_name="your_new_driver")` 