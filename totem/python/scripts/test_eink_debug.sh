#!/bin/bash
# E-Ink Display Debug Test Script
# Run this on the Raspberry Pi to diagnose E-Ink display issues

set -e  # Exit on error

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Activate the virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Make sure the test script is executable
chmod +x test_eink_debug.py

# Check if the GPIO pin values are properly set
echo "Checking GPIO pins..."
if [ -e "/sys/class/gpio/export" ]; then
    # Export pins if not already exported
    if [ ! -e "/sys/class/gpio/gpio17" ]; then
        echo "Exporting reset pin (17)..."
        echo 17 > /sys/class/gpio/export 2>/dev/null || true
    fi
    
    if [ ! -e "/sys/class/gpio/gpio25" ]; then
        echo "Exporting DC pin (25)..."
        echo 25 > /sys/class/gpio/export 2>/dev/null || true
    fi
    
    if [ ! -e "/sys/class/gpio/gpio24" ]; then
        echo "Exporting busy pin (24)..."
        echo 24 > /sys/class/gpio/export 2>/dev/null || true
    fi
    
    # Set directions
    if [ -e "/sys/class/gpio/gpio17" ]; then
        echo "Setting reset pin (17) as output..."
        echo out > /sys/class/gpio/gpio17/direction 2>/dev/null || true
    fi
    
    if [ -e "/sys/class/gpio/gpio25" ]; then
        echo "Setting DC pin (25) as output..."
        echo out > /sys/class/gpio/gpio25/direction 2>/dev/null || true
    fi
    
    if [ -e "/sys/class/gpio/gpio24" ]; then
        echo "Setting busy pin (24) as input..."
        echo in > /sys/class/gpio/gpio24/direction 2>/dev/null || true
    fi
fi

# Verify SPI is enabled
echo "Checking if SPI is enabled..."
if [ -e "/dev/spidev0.0" ]; then
    echo "SPI is enabled."
else
    echo "SPI device not found. Please make sure SPI is enabled in raspi-config."
    echo "You can enable it with: sudo raspi-config nonint do_spi 0"
    exit 1
fi

# Check permissions on SPI and GPIO devices
echo "Checking device permissions..."
ls -l /dev/spidev0.0
ls -l /dev/gpiochip0

# Configure Python logging
export TOTEM_LOG_LEVEL=DEBUG

# Run all tests
echo "Running E-Ink debug tests..."
python test_eink_debug.py --all

# If we get here, the script completed without errors
echo "Test script completed. Check the logs for details." 