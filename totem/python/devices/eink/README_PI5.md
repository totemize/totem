# E-Ink Display Driver for Raspberry Pi 5

This directory contains a special driver for the Waveshare 3.7" e-Paper HAT to work with Raspberry Pi 5.

## Why a Special Driver?

The traditional RPi.GPIO library doesn't work correctly on Raspberry Pi 5 due to hardware changes. When using RPi.GPIO, you'll see an error like:

```
RuntimeError: Cannot determine SOC peripheral base address
```

Our Pi 5 specific driver (`waveshare_3in7_pi5.py`) uses the `gpiod` library instead, which is fully compatible with Raspberry Pi 5.

## Installation

1. Install the required dependencies:

```bash
# Install system packages
sudo apt-get update
sudo apt-get install -y libgpiod-dev python3-libgpiod gpiod python3-pip python3-spidev

# Install the Python packages in your Poetry environment
poetry add gpiod spidev
```

2. The driver files are already in the correct location, and the detection system will automatically use the Pi 5 specific driver when running on a Raspberry Pi 5.

## Testing

You can test the e-ink display with the provided test script:

```bash
poetry run python test_pi5_eink.py
```

This script will:
1. Check if gpiod is available
2. Detect the Raspberry Pi model
3. Initialize the e-ink display
4. Display a test pattern

You can also use our quick test script:

```bash
python python/scripts/eink_quick_test.py
```

## Common Issues

### Missing spidev Module

If you see an error like:

```
Hardware initialization failed: name 'spidev' is not defined
```

It means the `spidev` Python module is not installed. This is a common issue when setting up the display for the first time. 

To fix this:

```bash
# Install using pip
sudo pip3 install spidev

# If using Poetry
poetry add spidev
```

Alternatively, run our automated fix script which handles all dependencies:

```bash
sudo python/scripts/fix_eink_dependencies.sh
```

For a comprehensive list of troubleshooting steps, see the `README_TROUBLESHOOTING.md` file.

## Troubleshooting

If you encounter issues:

1. Make sure required modules are correctly installed:
   ```bash
   python -c "import gpiod, spidev; print('Modules available')"
   ```

2. Check permissions:
   ```bash
   sudo usermod -a -G gpio,spi $USER
   # Log out and log back in
   ```

3. Enable SPI interface:
   ```bash
   sudo raspi-config nonint do_spi 0
   ```

4. Check the SPI devices:
   ```bash
   ls -l /dev/spidev*
   ```

5. Set correct permissions:
   ```bash
   sudo chmod 666 /dev/spidev0.0 /dev/spidev0.1 /dev/gpiochip0
   ```

6. Try running with sudo to rule out permission issues:
   ```bash
   sudo poetry run python test_pi5_eink.py
   ```

7. Run our diagnostic script for detailed analysis:
   ```bash
   python python/scripts/diagnose_eink.py
   ```

## Pin Connections

The driver is configured for the following GPIO pins:

- Reset: GPIO 17
- DC (Data/Command): GPIO 25
- Busy: GPIO 24
- CS (Chip Select): GPIO 8

If your hardware uses different pins, you'll need to modify the driver file. 