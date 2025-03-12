#!/bin/bash
# Script to execute the alternative E-Ink SPI test on the Raspberry Pi

# Make the target Python script executable
chmod +x eink_spi_alt_test.py

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

# Kill any existing Python processes that might be using GPIO
echo "Killing any Python processes that might be using GPIO..."
pkill -f python.*gpio || true

# Clean up any existing GPIO exports
echo "Cleaning up GPIO resources..."
if [ -d "/sys/class/gpio" ]; then
    for pin in 17 25 24 8 27 22 23 7; do
        if [ -e "/sys/class/gpio/gpio${pin}" ]; then
            echo "Unexport GPIO ${pin}..."
            echo ${pin} | sudo tee /sys/class/gpio/unexport >/dev/null 2>&1 || true
        fi
    done
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

# Check power supply voltage - low voltage can cause issues
if command -v vcgencmd >/dev/null; then
    echo "Checking power supply voltage..."
    vcgencmd measure_volts
    VOLTAGE=$(vcgencmd measure_volts | cut -d= -f2 | sed 's/V//')
    if (( $(echo "$VOLTAGE < 0.8" | bc -l) )); then
        echo "WARNING: Low voltage detected. This could cause instability."
        echo "Make sure you have a good power supply (5V/3A recommended)."
    fi
fi

# List available SPI devices
echo "Available SPI devices:"
ls -la /dev/spidev*

# Make sure the user has permissions to access SPI and GPIO
echo "Setting permissions for SPI and GPIO devices..."
for spidev in /dev/spidev*; do
    sudo chmod 666 $spidev
done

# Check for GPIO device and set permissions
if [ -e "/dev/gpiochip0" ]; then
    sudo chmod 666 /dev/gpiochip0
fi

if [ -d "/sys/class/gpio" ]; then
    sudo chmod -R 777 /sys/class/gpio || true
fi

# Stop NVMe service to avoid potential conflicts (optional)
echo "Checking for running NVMe-related services..."
running_services=$(systemctl list-units --full --all | grep -i nvme || true)
if [ -n "$running_services" ]; then
    echo "Found NVMe-related services:"
    echo "$running_services"
    read -p "Would you like to temporarily stop NVMe services to avoid conflicts? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl stop nvme* || true
        echo "NVMe services temporarily stopped."
    fi
fi

# Run the alternative E-Ink SPI test
echo "Running alternative E-Ink SPI test..."
sudo python3 eink_spi_alt_test.py

# Restart NVMe services if they were stopped
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restarting NVMe services..."
    sudo systemctl start nvme* || true
fi

echo "Test execution completed." 