#!/bin/bash
# Script to run EInk test in NVME-compatible mode
# This script sets up the environment to use alternative pins
# that don't conflict with the NVME hat

# Set up environment
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Export environment variables
export PYTHONPATH="${PYTHONPATH:-$PROJECT_ROOT}"
export NVME_COMPATIBLE=1
export EINK_MOCK_MODE=${EINK_MOCK_MODE:-0}

# Get message from command line or use default
MESSAGE="${1:-Hello Totem!}"

echo "Running EInk test in NVME-compatible mode"
echo "PYTHONPATH: $PYTHONPATH"
echo "NVME_COMPATIBLE: $NVME_COMPATIBLE"
echo "EINK_MOCK_MODE: $EINK_MOCK_MODE"
echo "Message: $MESSAGE"

# Check if GPIO pins are available
echo "Checking GPIO pin availability..."

# Define pins to check
RST_PIN=17
DC_PIN=25
CS_PIN=9
BUSY_PIN=24
MOSI_PIN=22
SCK_PIN=23

# Create a Python script to check GPIO availability
python3 - << EOF
import sys
try:
    import lgpio
    print("GPIO chip opened successfully")
    
    # Open GPIO chip
    h = lgpio.gpiochip_open(0)
    
    # Check pins
    pins = [$RST_PIN, $DC_PIN, $CS_PIN, $BUSY_PIN, $MOSI_PIN, $SCK_PIN]
    pin_names = ["RST", "DC", "CS", "BUSY", "MOSI", "SCK"]
    all_available = True
    
    for i, pin in enumerate(pins):
        try:
            # Try to claim the pin temporarily
            handle = lgpio.gpio_claim_input(h, pin)
            lgpio.gpio_free(h, pin)
            print(f"✓ Pin {pin} is free")
        except Exception as e:
            print(f"✗ Pin {pin} is busy: {e}")
            all_available = False
    
    print("")
    if all_available:
        print("All pins are available!")
    else:
        print("Some pins are busy. You may need to free them first.")
        print("Try running: sudo killall pigpiod")
    
    # Close GPIO chip
    lgpio.gpiochip_close(h)
    
except ImportError:
    print("lgpio module not available")
    sys.exit(1)
except Exception as e:
    print(f"Error checking GPIO pins: {e}")
    sys.exit(1)
EOF

# Check if the GPIO check was successful
if [ $? -ne 0 ]; then
    echo "Failed to check GPIO pins. Exiting."
    exit 1
fi

echo ""
echo "Sending message to EInk display..."

# Create a Python script to send a message to the EInk display
python3 - << EOF
import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

try:
    # Import the EInk driver
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    # Print configuration
    print("Running in NVME-compatible mode with software SPI")
    print("Using pins: RST=17, DC=25, CS=9, BUSY=24")
    print("Software SPI pins: MOSI=22, SCK=23")
    
    # Initialize the display
    display = WaveshareEPD3in7(
        mock_mode=os.environ.get('EINK_MOCK_MODE', '0') == '1',
        handle_errors=True,
        busy_timeout=15  # Increase timeout for more reliability
    )
    
    print(f"Mock mode: {display.mock_mode}")
    print(f"NVME compatible: {os.environ.get('NVME_COMPATIBLE', '0') == '1'}")
    print(f"Using software SPI: {display.using_sw_spi}")
    
    # Initialize the display
    print("Initializing display...")
    display.init()
    print("Display initialized")
    
    # Clear the display
    print("Clearing display...")
    display.clear()
    print("Display cleared")
    
    # Display text
    print("Displaying text...")
    
    # Create image with text
    message = """${MESSAGE}"""
    display.display_text(message)
    print("Text displayed")
    
    # Sleep the display
    print("Sleeping display...")
    display.sleep()
    
    # Clean up
    print("Cleaning up...")
    display.close()
    print("Display resources freed")
    
    print("Success! Message sent to EInk display")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

# Check if the display update was successful
if [ $? -ne 0 ]; then
    echo "Failed to update EInk display."
    exit 1
fi

exit 0 