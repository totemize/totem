#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Simple E-Ink Display Test Script

This script tests the E-Ink display using our consolidated driver
with an approach similar to the manufacturer's example, but using
simpler functions that don't require additional packages.
"""

import os
import sys
import time
import logging
import argparse

# Add the parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eink_test")

def main():
    """Main function to run the test"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Simple E-Ink Display Test')
    parser.add_argument('--mock', action='store_true', help='Use mock mode (no hardware)')
    parser.add_argument('--nvme', action='store_true', help='Use NVME compatibility mode')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Set environment variables
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
        logger.info("Using mock mode for display operations")
    
    if args.nvme:
        os.environ['NVME_COMPATIBLE'] = '1'
        logger.info("Using NVME compatibility mode")
    
    # Set busy timeout to be longer than default
    os.environ['EINK_BUSY_TIMEOUT'] = '10'
    
    try:
        # Try to import the driver with different paths
        try:
            # Try to import from python path
            from python.devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
            logger.info("Imported driver from python.devices.eink.drivers")
        except ImportError:
            try:
                # Try to import directly
                from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
                logger.info("Imported driver from devices.eink.drivers")
            except ImportError as e:
                logger.error(f"Failed to import driver: {e}")
                # Add helpful information
                logger.error("Make sure the consolidated driver is in the correct location:")
                logger.error("  - python/devices/eink/drivers/waveshare_3in7.py")
                raise
        
        # Initialize the display
        logger.info("Initializing E-Ink display")
        epd = WaveshareEPD3in7()
        
        # Print display configuration
        logger.info(f"E-Ink Display Configuration:")
        logger.info(f"  Mock mode: {epd.mock_mode}")
        logger.info(f"  NVME compatible: {epd.nvme_compatible}")
        logger.info(f"  Software SPI: {epd.using_sw_spi}")
        logger.info(f"  Width x Height: {epd.width} x {epd.height}")
        
        # Initialize with 4Gray mode like manufacturer's example
        logger.info("Initializing display in 4Gray mode")
        epd.init(0)  # 0 = 4Gray mode
        
        # Clear the display
        logger.info("Clearing display")
        epd.Clear()
        
        # Display test text
        logger.info("Displaying text")
        epd.display_text("Simple Test", 10, 10, 36)
        logger.info("Waiting for 3 seconds...")
        time.sleep(3)
        
        # Display more text
        logger.info("Displaying additional text")
        epd.display_text("Totem 3.7\" E-Ink", 10, 50, 24)
        logger.info("Waiting for 3 seconds...")
        time.sleep(3)
        
        # Display success message
        logger.info("Displaying success message")
        epd.Clear()
        epd.display_text("Test Complete", 10, 10, 36)
        epd.display_text("SUCCESS!", 10, 50, 36)
        
        # Sleep the display to save power
        logger.info("Putting display to sleep")
        epd.sleep()
        
        logger.info("Test completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during E-Ink display test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 