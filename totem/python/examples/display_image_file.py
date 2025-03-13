#!/usr/bin/env python3
"""
Display Image File Example

This script demonstrates how to display an image file on the e-ink display
using the new display_file method.

Usage:
    python3 display_image_file.py [/path/to/image.png]
    
If no image path is provided, it will use the default bitmap sample from the assets folder.
The image will be automatically converted to grayscale and resized to fit the display.
Supported formats include PNG, JPG, BMP, and others supported by PIL.

Run with sudo for proper GPIO access:
    sudo python3 display_image_file.py [/path/to/image.png]
"""

import os
import sys
import time
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eink_image")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Display an image file on the e-ink display')
    parser.add_argument('image_path', nargs='?', help='Path to the image file to display (optional)')
    parser.add_argument('--no-resize', action='store_true', help='Do not resize the image to fit the display')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode (no hardware required)')
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() != 0 and not args.mock:
        logger.error("This script must be run as root (sudo) to access GPIO pins. Use --mock for testing without hardware.")
        sys.exit(1)
    
    # Add the project root to the Python path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    sys.path.insert(0, project_root)
    
    # If no image path is provided, use the default bitmap sample
    if args.image_path is None:
        default_image_path = os.path.join(project_root, "python", "assets", "bitmap-sample.bmp")
        if os.path.exists(default_image_path):
            args.image_path = default_image_path
            logger.info(f"Using default bitmap sample: {default_image_path}")
        else:
            logger.error("Default bitmap sample not found. Please provide an image path.")
            sys.exit(1)
    
    # Check if the image file exists
    if not os.path.exists(args.image_path):
        logger.error(f"Image file not found: {args.image_path}")
        sys.exit(1)
    
    # Set mock mode if requested
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
        logger.info("Running in mock mode (no hardware required)")
    
    try:
        # Import the driver
        logger.info("Importing driver...")
        from python.devices.eink.drivers.waveshare_3in7 import Driver
        
        # Initialize the driver
        logger.info("Initializing driver...")
        driver = Driver()
        driver.init()
        
        # Display the image file
        logger.info(f"Displaying image: {args.image_path}")
        driver.display_file(args.image_path, resize=not args.no_resize)
        
        # Wait a moment to ensure the display has time to update
        time.sleep(2)
        
        logger.info("Image displayed successfully!")
        
        # Put the display to sleep
        logger.info("Putting display to sleep...")
        driver.sleep()
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 