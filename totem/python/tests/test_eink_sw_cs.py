#!/usr/bin/env python3
"""
Test script for the E-Ink display with software CS control
This script tests the modified driver that uses software CS control to avoid conflicts with the NVMe HAT
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('eink_sw_cs_test.log')
    ]
)

logger = logging.getLogger(__name__)

def test_display_clear():
    """Test clearing the display using software CS control"""
    logger.info("Testing E-Ink display clear with software CS control")
    
    try:
        # Import the driver with software CS control
        from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
        
        # Create driver instance
        logger.info("Creating driver instance")
        driver = Driver()
        
        # Enable debug mode for detailed logging
        driver.enable_debug_mode(True)
        
        # Initialize the display
        logger.info("Initializing display")
        driver.init()
        
        # Check if we're using hardware
        if not driver.USE_HARDWARE:
            logger.warning("Hardware not available, running in mock mode")
            
        # Clear the display
        logger.info("Clearing display")
        driver.clear()
        
        # Wait a moment to see the result
        logger.info("Waiting for result to be visible")
        time.sleep(3)
        
        # Put the display to sleep
        logger.info("Putting display to sleep")
        driver.sleep()
        
        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_display_pattern():
    """Test displaying a simple pattern using software CS control"""
    logger.info("Testing E-Ink pattern display with software CS control")
    
    try:
        # Import the driver with software CS control
        from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
        
        # Create driver instance
        logger.info("Creating driver instance")
        driver = Driver()
        
        # Enable debug mode for detailed logging
        driver.enable_debug_mode(True)
        
        # Initialize the display
        logger.info("Initializing display")
        driver.init()
        
        # Check if we're using hardware
        if not driver.USE_HARDWARE:
            logger.warning("Hardware not available, running in mock mode")
            return False
            
        # Create a simple pattern - alternating black and white stripes
        width = driver.width
        height = driver.height
        
        # Calculate the buffer size (width * height / 8)
        buffer_size = width * height // 8
        
        # Create a pattern - horizontal stripes
        pattern = []
        for i in range(buffer_size):
            # Each byte represents 8 pixels
            # 0x55 = 01010101 (alternating black/white)
            # 0xAA = 10101010 (alternating white/black)
            if (i // (width // 8)) % 2 == 0:
                pattern.append(0x55)
            else:
                pattern.append(0xAA)
        
        # Display the pattern
        logger.info(f"Displaying pattern (size: {len(pattern)} bytes)")
        driver.display_bytes(bytes(pattern))
        
        # Wait a moment to see the result
        logger.info("Waiting for result to be visible")
        time.sleep(5)
        
        # Clear the display
        logger.info("Clearing display")
        driver.clear()
        
        # Wait a moment to see the result
        time.sleep(2)
        
        # Put the display to sleep
        logger.info("Putting display to sleep")
        driver.sleep()
        
        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_with_alternative_pins():
    """Test using alternative pins (specified by environment variables)"""
    logger.info("Testing E-Ink display with alternative pins")
    
    try:
        # Set environment variables for alternative pins
        os.environ['USE_ALT_EINK_PINS'] = '1'
        os.environ['EINK_RST_PIN'] = '27'
        os.environ['EINK_DC_PIN'] = '22'
        os.environ['EINK_BUSY_PIN'] = '23'
        os.environ['EINK_CS_PIN'] = '7'
        
        # Import the driver with software CS control
        from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
        
        # Create driver instance
        logger.info("Creating driver instance with alternative pins")
        driver = Driver()
        
        # Enable debug mode for detailed logging
        driver.enable_debug_mode(True)
        
        # Initialize the display
        logger.info("Initializing display")
        driver.init()
        
        # Check if we're using hardware
        if not driver.USE_HARDWARE:
            logger.warning("Hardware not available, running in mock mode")
            
        # Clear the display
        logger.info("Clearing display")
        driver.clear()
        
        # Wait a moment to see the result
        logger.info("Waiting for result to be visible")
        time.sleep(3)
        
        # Put the display to sleep
        logger.info("Putting display to sleep")
        driver.sleep()
        
        # Clean up environment variables
        del os.environ['USE_ALT_EINK_PINS']
        del os.environ['EINK_RST_PIN']
        del os.environ['EINK_DC_PIN']
        del os.environ['EINK_BUSY_PIN']
        del os.environ['EINK_CS_PIN']
        
        logger.info("Test with alternative pins completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test with alternative pins failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main test function"""
    logger.info("=== E-Ink Software CS Test ===")
    
    # Run tests
    results = []
    
    logger.info("Running display clear test...")
    clear_result = test_display_clear()
    results.append(("Display Clear", clear_result))
    
    logger.info("Running pattern test...")
    pattern_result = test_display_pattern()
    results.append(("Pattern Display", pattern_result))
    
    logger.info("Running alternative pins test...")
    alt_pins_result = test_with_alternative_pins()
    results.append(("Alternative Pins", alt_pins_result))
    
    # Report results
    logger.info("=== Test Results ===")
    success = True
    for test_name, result in results:
        logger.info(f"{test_name}: {'PASS' if result else 'FAIL'}")
        success = success and result
    
    if success:
        logger.info("All tests passed!")
        return 0
    else:
        logger.warning("Some tests failed. Check the log for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 