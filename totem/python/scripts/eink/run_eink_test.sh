#!/bin/bash
# Script to execute the E-Ink SPI test on the Raspberry Pi

# Make the target Python script executable
chmod +x eink_spi_test.py

# Check if RPi.GPIO is installed
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
    echo "Installing RPi.GPIO..."
    sudo pip3 install RPi.GPIO
fi

# Check if spidev is installed
if ! python3 -c "import spidev" 2>/dev/null; then
    echo "Installing spidev..."
    sudo pip3 install spidev
fi

# Make sure SPI is enabled
if ! ls /dev/spidev* >/dev/null 2>&1; then
    echo "SPI interface not found. Enabling SPI..."
    # Check if raspi-config exists (Raspberry Pi OS)
    if command -v raspi-config >/dev/null; then
        sudo raspi-config nonint do_spi 0
    else
        echo "raspi-config not found. Please enable SPI manually."
        exit 1
    fi
fi

# Make sure the user has permissions to access SPI and GPIO
echo "Setting permissions for SPI and GPIO devices..."
for spidev in /dev/spidev*; do
    sudo chmod 666 $spidev
done

# Check for GPIO device and set permissions
if [ -d "/sys/class/gpio" ]; then
    sudo chmod -R 666 /sys/class/gpio
fi

if [ -e "/dev/gpiochip0" ]; then
    sudo chmod 666 /dev/gpiochip0
fi

# Kill any existing Python processes that might be using GPIO
echo "Killing any Python processes that might be using GPIO..."
pkill -f python.*gpio

# Run the E-Ink SPI test
echo "Running E-Ink SPI test..."
sudo python3 eink_spi_test.py

echo "Test execution completed." 