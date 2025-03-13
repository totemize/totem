#!/bin/bash
# Run EInk test in NVME-compatible mode
# This script is designed to work with both the EInk display and NVME hat simultaneously

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Set environment variables for NVME compatibility mode
export NVME_COMPATIBLE=1
export PYTHONPATH="${TOTEM_DIR}"

# Optionally use mock mode if no physical display is connected
export EINK_MOCK_MODE=${EINK_MOCK_MODE:-0}  # Set to 1 to use mock mode

# Get the message to display from the command line argument
MESSAGE="${1:-"EInk + NVME\nCompatible Mode\nWorking!"}"

echo "Running EInk test in NVME-compatible mode"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "NVME_COMPATIBLE: ${NVME_COMPATIBLE}"
echo "EINK_MOCK_MODE: ${EINK_MOCK_MODE}"
echo "Message: ${MESSAGE}"

# First check if GPIO pins are free
echo "Checking GPIO pin availability..."
python3 - << EOF
import os
import sys
sys.path.insert(0, "${TOTEM_DIR}")
import lgpio

def test_pin(h, pin):
    try:
        handle = lgpio.gpio_claim_output(h, pin, 0)
        print(f"✓ Pin {pin} is free")
        lgpio.gpio_free(h, pin)
        return True
    except Exception as e:
        print(f"✗ Pin {pin} is busy: {e}")
        return False

try:
    h = lgpio.gpiochip_open(0)
    print("GPIO chip opened successfully")
    
    # Test pins we plan to use
    pins = [17, 25, 9, 24, 22, 23]  # RST, DC, CS, BUSY, MOSI, SCK
    
    all_free = True
    for pin in pins:
        if not test_pin(h, pin):
            all_free = False
    
    lgpio.gpiochip_close(h)
    
    if all_free:
        print("\nAll pins are available!")
    else:
        print("\nSome pins are busy. Using alternative pins or mock mode may be necessary.")
except Exception as e:
    print(f"Error: {e}")
EOF

# Create a simple Python script to send the message to the EInk display
echo -e "\nSending message to EInk display..."

python3 - << EOF
import os
import sys
import time
sys.path.insert(0, "${TOTEM_DIR}")

try:
    # Import using the correct path
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    # Initialize display with environment variables already set by the script
    epd = WaveshareEPD3in7()
    print(f"Mock mode: {epd.mock_mode}")
    print(f"NVME compatible: {epd.nvme_compatible}")
    print(f"Using software SPI: {epd.using_sw_spi}")
    
    # Initialize the display
    print("Initializing display...")
    epd.init()
    print("Display initialized")
    
    # Clear the display
    print("Clearing display...")
    epd.Clear()
    print("Display cleared")
    
    # Display text (allow multiline text with \n)
    print("Displaying text...")
    lines = """${MESSAGE}""".split('\\n')
    y_position = 10
    for line in lines:
        epd.display_text(line, 10, y_position, 36)
        y_position += 50
    print("Text displayed")
    
    # Sleep
    print("Sleeping display...")
    epd.sleep()
    
    # Clean up
    print("Cleaning up...")
    epd.close()
    
    print("Success! Message sent to EInk display")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
EOF

exit $? 