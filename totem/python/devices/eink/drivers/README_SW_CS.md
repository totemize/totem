# E-Ink Display Driver with Software CS Control

This directory contains a modified version of the Waveshare 2.13inch E-Ink display driver that uses software CS control instead of hardware CS. This is useful when the hardware CS pin conflicts with other hardware, such as the NVMe HAT on the Raspberry Pi.

## Problem Background

Our testing revealed that the NVMe HAT conflicts with the E-Ink display's CS pin (GPIO 8). When both are connected, the E-Ink display fails to initialize properly or update. This is likely because both devices are attempting to use the same GPIO pin.

## Solution

The `waveshare_2in13_pi5_sw_cs.py` driver implements software CS control instead of relying on the hardware CS pin. This allows the driver to work correctly even when the hardware CS pin is in use by another device.

## How to Use

1. Pull the latest code from the repository:
   ```
   cd ~/totem
   git pull
   ```

2. Navigate to the test directory:
   ```
   cd totem/python/tests
   ```

3. Make the test script executable:
   ```
   chmod +x run_eink_sw_cs_test.sh
   ```

4. Run the test script:
   ```
   ./run_eink_sw_cs_test.sh
   ```

5. Check the results:
   - The script will output the test results to the console and save them to `eink_sw_cs_test_results.log`.
   - If the tests pass, the display should show a pattern of black and white stripes, then clear to white.

## Alternative Pin Configuration

If you need to use different GPIO pins, you can set the following environment variables before running your code:

```bash
export USE_ALT_EINK_PINS=1
export EINK_RST_PIN=27   # Default: 17
export EINK_DC_PIN=22    # Default: 25
export EINK_BUSY_PIN=23  # Default: 24
export EINK_CS_PIN=7     # Default: 8
```

Or modify your code to set these environment variables:

```python
import os
os.environ['USE_ALT_EINK_PINS'] = '1'
os.environ['EINK_RST_PIN'] = '27'
os.environ['EINK_DC_PIN'] = '22'
os.environ['EINK_BUSY_PIN'] = '23'
os.environ['EINK_CS_PIN'] = '7'

# Then import and use the driver
from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
```

## Using in Your Own Code

To use this driver in your own code, simply import the Driver class from the software CS driver instead of the standard driver:

```python
# Import the driver with software CS control
from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver

# Create driver instance
driver = Driver()

# Enable debug mode for detailed logging (optional)
driver.enable_debug_mode(True)

# Initialize the display
driver.init()

# Clear the display
driver.clear()

# To display an image (requires PIL)
from PIL import Image
image = Image.open('your_image.png')
driver.display_image(image)

# When done, put the display to sleep
driver.sleep()
```

## Troubleshooting

If you're still having issues with the E-Ink display:

1. Make sure all required pins (RST, DC, BUSY) are free and not in use by other devices.
2. Check the log file for detailed error messages.
3. Ensure the SPI interface is enabled on your Raspberry Pi:
   ```
   sudo raspi-config nonint do_spi 0
   ```
4. Make sure the user has permissions to access SPI and GPIO devices:
   ```
   sudo chmod 666 /dev/spidev*
   sudo chmod 666 /dev/gpiochip0
   ```
5. Try using the alternative pin configuration as described above.

## How It Works

The driver uses the following approach to implement software CS control:

1. It still initializes the CS pin as an output GPIO pin.
2. Before sending any data via SPI, it manually sets the CS pin to LOW (active).
3. After sending data, it manually sets the CS pin back to HIGH (inactive).
4. If the CS pin is in use by another device, the driver can still function without it (though with potentially reduced reliability).

This approach works because the SPI communication can still occur without hardware CS if the software ensures proper timing and control. 