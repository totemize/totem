#!/bin/bash
# Run final EInk test with the most reliable configuration
# Uses pin 9 for CS and handles busy pin properly

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Set environment variables for alternative pins
export USE_ALT_EINK_PINS=1
export EINK_RST_PIN=17  # Default is 17, which is free
export EINK_DC_PIN=25   # Default is 25, which is free
export EINK_CS_PIN=9    # Use pin 9 instead of 8 (which is busy)
export EINK_BUSY_PIN=24 # Default is 24, which is free
export PYTHONPATH="${TOTEM_DIR}"

# Enable software SPI mode
export USE_SW_SPI=1
export EINK_MOSI_PIN=10 # Default is 10, which is free
export EINK_SCK_PIN=11  # Default is 11, which is free

# Environment variables for better error handling
export EINK_HANDLE_ERRORS=1  # Enable fallback to mock mode on errors
export EINK_BUSY_TIMEOUT=3   # Shorter timeout for busy pin (seconds)

echo "Running final EInk test with optimal configuration"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Using pins: RST=${EINK_RST_PIN}, DC=${EINK_DC_PIN}, CS=${EINK_CS_PIN}, BUSY=${EINK_BUSY_PIN}"
echo "Software SPI pins: MOSI=${EINK_MOSI_PIN}, SCK=${EINK_SCK_PIN}"
echo "Software SPI: ${USE_SW_SPI}"
echo "Error handling: Enabled, Busy timeout: ${EINK_BUSY_TIMEOUT}s"

# First run the GPIO test to verify pins
echo "Verifying GPIO pins..."
python3 python/tests/test_eink_diagnostics.py --pin ${EINK_CS_PIN} --test gpio

# Then run the full test
echo -e "\nRunning EInk display test..."

# Create a custom Python program that initializes the display, clears it, and displays text
python3 - << EOL
import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('eink_test')

# Add project root to path
sys.path.insert(0, '${TOTEM_DIR}')

# Import the EInk driver
from python.devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7

try:
    # Initialize
    logger.info("Initializing EInk display")
    epd = WaveshareEPD3in7()
    
    # Set shorter busy timeout
    epd.busy_timeout = int(os.environ.get('EINK_BUSY_TIMEOUT', 3))
    
    # Initialize display
    epd.init()
    logger.info("Display initialized")
    
    # Clear the display
    logger.info("Clearing display")
    epd.Clear()
    logger.info("Display cleared")
    
    # Display text
    logger.info("Displaying text")
    epd.display_text("totem.", 50, 50, 48)
    logger.info("Text displayed")
    
    # Sleep
    logger.info("Putting display to sleep")
    epd.sleep()
    
    # Clean up
    logger.info("Cleaning up")
    epd.close()
    
    logger.info("Test completed successfully!")
    sys.exit(0)
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOL

exit $? 