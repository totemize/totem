# Waveshare 2.13inch E-Paper HAT (250×122) Quick Start Guide

This guide covers the setup and usage of the Waveshare 2.13-inch E-Paper HAT with the totem framework on Raspberry Pi.

## Technical Specifications

- **Resolution**: 250 × 122 pixels
- **Display Color**: Black and White
- **Interface**: SPI
- **Viewing Angle**: >170°
- **Power Consumption**: 26.4mW (typical refresh power)
- **Standby Current**: <0.01uA
- **Operating Voltage**: 3.3V/5V
- **Driver IC**: Unknown (Waveshare proprietary)

## Hardware Setup

1. **Power off** your Raspberry Pi before connecting the E-Paper HAT.
2. Carefully **connect the E-Paper HAT** to the Raspberry Pi GPIO pins, ensuring the pins are aligned correctly.
3. **Power on** your Raspberry Pi.

## Pin Connections

The 2.13-inch E-Paper HAT uses the following connections:

| E-Paper HAT | Raspberry Pi GPIO |
|-------------|-------------------|
| VCC         | 3.3V              |
| GND         | GND               |
| DIN         | GPIO 10 (MOSI)    |
| CLK         | GPIO 11 (SCLK)    |
| CS          | GPIO 8 (CE0)      |
| DC          | GPIO 25           |
| RST         | GPIO 17           |
| BUSY        | GPIO 24           |

## Software Setup

### 1. System Requirements

Ensure your Raspberry Pi has the required dependencies:

```bash
cd /path/to/totem/python/scripts
sudo ./fix_eink_dependencies.sh
```

This script will:
- Install required system packages (python3-pip, python3-dev, etc.)
- Install required Python packages (spidev, numpy, pillow, gpiod)
- Enable the SPI interface
- Set appropriate permissions for SPI and GPIO devices
- Add your user to the gpio group

### 2. Testing the Display

After installing dependencies and rebooting (if required), run the test script:

```bash
cd /path/to/totem/python/scripts
python3 test_2in13_eink.py
```

This script will:
1. Initialize the display
2. Clear the display
3. Show a test pattern
4. Display text information
5. Put the display to sleep

## Using the Display in Your Code

### Basic Example

```python
from devices.eink.drivers.waveshare_2in13 import Driver
# Or for Raspberry Pi 5:
# from devices.eink.drivers.waveshare_2in13_pi5 import Driver

from PIL import Image, ImageDraw, ImageFont
import time

# Initialize the driver
eink = Driver()
eink.init()

# Create a blank white image
image = Image.new('1', (eink.width, eink.height), 255)
draw = ImageDraw.Draw(image)

# Draw some text
font = ImageFont.load_default()
draw.text((10, 10), "Hello, E-Paper!", font=font, fill=0)

# Display the image
eink.display_image(image)

# Put the display to sleep when done
time.sleep(5)
eink.sleep()
```

### Displaying Images

```python
from devices.eink.drivers.waveshare_2in13 import Driver
from PIL import Image
import os

# Initialize the driver
eink = Driver()
eink.init()

# Load an image (must be 250x122 pixels)
image_path = "path/to/your/image.png"
if os.path.exists(image_path):
    image = Image.open(image_path)
    # Convert to 1-bit mode (black and white)
    image = image.convert('1')
    # Resize if needed
    image = image.resize((eink.width, eink.height))
    # Display
    eink.display_image(image)
```

## Troubleshooting

If you encounter issues, please refer to the full troubleshooting guide at:
`/python/devices/eink/README_TROUBLESHOOTING.md`

Common issues include:
- Missing spidev module
- Permission denied for SPI or GPIO devices
- SPI interface not enabled
- Hardware connections incorrect

## Power Management

The E-Paper display retains its image even when powered off (one of its key features). To conserve power:

1. Call `eink.sleep()` to put the display into deep sleep mode when not in use.
2. Only update the display when necessary, as each refresh consumes power.

## Hardware Limitations

- **Refresh Rate**: The display has a slow refresh rate (~2-3 seconds), making it unsuitable for animation or frequently updated content.
- **Partial Refresh**: While the display supports partial refresh, it may sometimes show artifacts and require a full refresh to clear them.
- **Temperature Sensitivity**: The display may perform differently in extreme temperatures.

## Resources

- [Waveshare Wiki for 2.13inch e-Paper HAT](https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT)
- [SPI Interface Documentation](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md)
- [GPIO Programming in Python](https://gpiozero.readthedocs.io/) 