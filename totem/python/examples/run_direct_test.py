#!/usr/bin/env python3
"""
Direct Test of Waveshare E-Ink Display

This script directly uses our Driver class which has better error handling.
It performs a similar test to the manufacturer's example but uses our wrapper.

Run with sudo for proper GPIO access:
    sudo python3 run_direct_test.py
"""

import os
import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("eink_test")

def main():
    # Check if running as root
    if os.geteuid() != 0:
        logger.error("This script must be run as root (sudo). Exiting.")
        sys.exit(1)
    
    # Add our local package to the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # Try different possible paths to find the driver
    possible_paths = [
        os.path.join(project_root, "devices", "eink", "drivers"),
        os.path.join(project_root, "python", "devices", "eink", "drivers"),
        os.path.join(os.path.dirname(project_root), "devices", "eink", "drivers"),
        os.path.join(os.path.dirname(project_root), "python", "devices", "eink", "drivers"),
    ]
    
    driver_path = None
    for path in possible_paths:
        if os.path.exists(path):
            driver_path = path
            logger.info(f"Found drivers directory at: {path}")
            sys.path.insert(0, os.path.dirname(os.path.dirname(path)))
            break
    
    if not driver_path:
        logger.error("Could not find drivers directory. Please check your project structure.")
        sys.exit(1)
    
    # Try to import the driver
    try:
        from devices.eink.drivers.waveshare_3in7 import Driver
        logger.info("Successfully imported Driver class")
    except ImportError as e:
        try:
            from python.devices.eink.drivers.waveshare_3in7 import Driver
            logger.info("Successfully imported Driver class (from python path)")
        except ImportError as e2:
            logger.error(f"Failed to import Driver: {e2}")
            sys.exit(1)
    
    # Import other required packages
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Failed to import PIL. Please install it with: sudo apt-get install python3-pil")
        sys.exit(1)
    
    # Find a suitable font
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    ]
    
    font36 = None
    font24 = None
    font18 = None
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                font36 = ImageFont.truetype(path, 36)
                font24 = ImageFont.truetype(path, 24)
                font18 = ImageFont.truetype(path, 18)
                logger.info(f"Using font: {path}")
                break
            except Exception:
                pass
    
    if font36 is None:
        logger.warning("No TrueType fonts found, using default")
        font36 = ImageFont.load_default()
        font24 = ImageFont.load_default()
        font18 = ImageFont.load_default()
    
    # Run the test
    try:
        logger.info("E-Ink Display Test")
        
        # Initialize the driver
        driver = Driver()
        logger.info("Initializing display...")
        driver.init()
        driver.clear()
        
        # Test display_text method
        logger.info("Testing display_text method...")
        driver.display_text("Hello from Totem!", 10, 10, 36)
        time.sleep(3)
        
        # Draw on the display
        logger.info("Drawing on the display...")
        Himage = Image.new('L', (driver.width, driver.height), 0xFF)  # 0xFF: clear the frame
        draw = ImageDraw.Draw(Himage)
        
        # Draw text
        draw.text((10, 0), 'Hello from Totem!', font=font24, fill=0)
        draw.text((10, 30), '3.7inch E-Ink Test', font=font24, fill=0)
        
        # Draw shapes with different gray levels
        draw.rectangle((10, 70, 150, 110), 'black', 'black')
        draw.text((10, 70), 'Waveshare', font=font36, fill=driver.GRAY1)
        draw.text((10, 120), 'E-Paper', font=font36, fill=driver.GRAY2)
        draw.text((10, 170), 'Demo', font=font36, fill=driver.GRAY3)
        draw.text((10, 220), 'Test', font=font36, fill=driver.GRAY4)
        
        # Draw lines and shapes
        draw.line((180, 50, 230, 100), fill=0)
        draw.line((230, 50, 180, 100), fill=0)
        draw.rectangle((180, 50, 230, 100), outline=0)
        draw.arc((240, 50, 290, 100), 0, 360, fill=0)
        draw.rectangle((300, 50, 350, 100), fill=0)
        
        # Display the image
        logger.info("Displaying image...")
        driver.display_image(Himage)
        
        # Wait for 5 seconds
        logger.info("Waiting for 5 seconds...")
        time.sleep(5)
        
        # Clear the display
        logger.info("Clearing display...")
        driver.clear()
        
        # Display text at different positions
        logger.info("Displaying text at different positions...")
        driver.display_text("Top Left", 10, 10, 24)
        driver.display_text("Top Right", 300, 10, 24)
        driver.display_text("Bottom Left", 10, 200, 24)
        driver.display_text("Bottom Right", 300, 200, 24)
        driver.display_text("Center", 200, 120, 36)
        
        # Wait for 5 seconds
        time.sleep(5)
        
        # Clear the display
        logger.info("Clearing display...")
        driver.clear()
        
        # Put the display to sleep
        logger.info("Putting display to sleep...")
        driver.sleep()
        
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to clean up
        try:
            driver.close()
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    main() 