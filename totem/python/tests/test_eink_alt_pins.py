#!/usr/bin/env python3
"""
Test script for EInk display with alternative GPIO pins
Uses pin 7 for CS instead of pin 8 to avoid conflict with SPI0 CS0
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add the parent directory to path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, os.path.dirname(python_dir))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("eink_test")

# Set environment variables for alternative pins
os.environ['USE_ALT_EINK_PINS'] = '1'
os.environ['EINK_CS_PIN'] = '7'  # Use pin 7 instead of pin 8 for CS

def test_eink_hardware():
    """Test the EInk display with hardware access"""
    try:
        from devices.eink.waveshare_3in7 import WaveshareEPD3in7
        
        logger.info("Initializing EInk display with alternative pins")
        logger.info(f"Using CS_PIN = {os.environ.get('EINK_CS_PIN', '7')}")
        
        # Initialize the display
        epd = WaveshareEPD3in7()
        epd.init()
        
        # Clear the display
        logger.info("Clearing display")
        epd.Clear()
        time.sleep(1)
        
        # Display text
        logger.info("Displaying text")
        epd.display_text("Hello Alt Pins! CS=7", 10, 10, 36)
        time.sleep(2)
        
        # Clear again
        logger.info("Clearing display again")
        epd.Clear()
        
        # Sleep
        logger.info("Putting display to sleep")
        epd.sleep()
        
        # Clean up
        logger.info("Cleaning up")
        epd.close()
        
        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting EInk test with alternative pins")
    success = test_eink_hardware()
    if success:
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed")
    sys.exit(0 if success else 1) 