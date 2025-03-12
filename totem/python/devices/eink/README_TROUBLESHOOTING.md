# E-Ink Display Troubleshooting Guide

This guide provides solutions for common issues encountered with the Waveshare 3.7inch E-Ink display on Raspberry Pi 5.

## Common Issues and Solutions

### Missing `spidev` Module Error

**Error Message:**
```
Hardware initialization failed: name 'spidev' is not defined
Error traceback: Traceback (most recent call last):
  File ".../python/devices/eink/drivers/waveshare_3in7_pi5.py", line 128, in __init__
    self.spi = spidev.SpiDev()
               ^^^^^^
NameError: name 'spidev' is not defined
```

**Solution:**
Run the fix dependencies script to install all required packages:
```bash
sudo python/scripts/fix_eink_dependencies.sh
```

This script will install the necessary Python packages (including spidev), enable the SPI interface, and set up the correct permissions.

### Permission Denied for SPI or GPIO Devices

**Error Messages:**
```
Failed to open SPI device: [Errno 13] Permission denied: '/dev/spidev0.0'
```
or
```
Failed to access GPIO: Permission denied
```

**Solution:**
Fix the permissions on the SPI and GPIO devices:

```bash
sudo chmod 666 /dev/spidev0.0 /dev/spidev0.1
sudo chmod 666 /dev/gpiochip0
sudo usermod -a -G gpio $USER
```

Then log out and log back in for the group changes to take effect, or run the fix script:

```bash
sudo python/scripts/fix_eink_dependencies.sh
```

### SPI Interface Not Enabled

**Error Message:**
```
SPI device /dev/spidev0.0 not found! Make sure SPI is enabled.
```

**Solution:**
Enable the SPI interface using raspi-config:

```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```

Or run the fix script which will enable SPI and configure everything:

```bash
sudo python/scripts/fix_eink_dependencies.sh
```

### Hardware Mode Not Available (Using Mock Mode)

**Warning Message:**
```
Hardware mode: DISABLED (mock mode)
```

**Solution:**
This usually means the driver couldn't access the hardware. Check:

1. Verify all hardware connections are correct according to the Waveshare pinout
2. Run the fix script to ensure all dependencies and configurations are correct:

```bash
sudo python/scripts/fix_eink_dependencies.sh
```

## Testing the Display

To verify the E-Ink display is working properly, run the test script:

```bash
python python/scripts/eink_quick_test.py
```

This will perform a basic test of the display, showing a pattern and text if successful.

For more detailed diagnostics:

```bash
python python/scripts/diagnose_eink.py
```

## Manual Installation Steps

If you prefer to manually install the dependencies, follow these steps:

1. Install required system packages:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-dev python3-setuptools python3-wheel python3-gpiod libgpiod-dev i2c-tools spi-tools
   ```

2. Install required Python packages:
   ```bash
   sudo pip3 install spidev numpy pillow gpiod
   ```

3. Enable SPI interface:
   ```bash
   sudo raspi-config nonint do_spi 0
   ```

4. Set permissions:
   ```bash
   sudo chmod 666 /dev/spidev0.0 /dev/spidev0.1
   sudo chmod 666 /dev/gpiochip0
   sudo usermod -a -G gpio $USER
   ```

5. Create persistent permissions with udev:
   ```bash
   sudo tee /etc/udev/rules.d/99-spi-gpio.rules > /dev/null << EOF
   SUBSYSTEM=="spidev", GROUP="gpio", MODE="0660"
   SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
   SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
   EOF
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

6. Reboot the system:
   ```bash
   sudo reboot
   ```

## Additional Resources

- [Waveshare 3.7inch E-Paper Wiki](https://www.waveshare.com/wiki/3.7inch_e-Paper_HAT)
- [SPI Interface Documentation](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md)
- [GPIO Programming in Python](https://gpiozero.readthedocs.io/en/stable/) 