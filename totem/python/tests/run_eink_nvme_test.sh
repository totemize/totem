#!/bin/bash
# Script to run the E-Ink and NVMe conflict test

# Make the script executable
chmod +x eink_nvme_conflict_test.py

# Kill any existing Python processes that might be using GPIO
echo "Killing any Python processes that might be using GPIO..."
sudo pkill -9 -f python || echo "No Python processes to kill"

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

# Run the test
echo "Running E-Ink and NVMe conflict test..."
sudo python3 eink_nvme_conflict_test.py | tee eink_nvme_test_results.log

# Check the exit code
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "Test completed successfully."
else
    echo "Test failed. Check the log file for details."
fi

echo "Test results saved to eink_nvme_test_results.log" 