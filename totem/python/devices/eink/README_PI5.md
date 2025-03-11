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
sudo apt-get install -y libgpiod-dev python3-libgpiod gpiod

# Install the Python packages in your Poetry environment
poetry add gpiod
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

## Troubleshooting

If you encounter issues:

1. Make sure gpiod is correctly installed:
   ```bash
   python -c "import gpiod; print('gpiod available')"
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

5. Try running with sudo to rule out permission issues:
   ```bash
   sudo poetry run python test_pi5_eink.py
   ```

## Pin Connections

The driver is configured for the following GPIO pins:

- Reset: GPIO 17
- DC (Data/Command): GPIO 25
- Busy: GPIO 24
- CS (Chip Select): GPIO 8

If your hardware uses different pins, you'll need to modify the driver file. 