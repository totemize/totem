#!/usr/bin/env python3
"""
Direct Test of Waveshare E-Ink Display

This script directly uses our local waveshare_epd package without requiring installation.
It performs the same test as the manufacturer's example but uses our local package.

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
    
    # Add our local waveshare_epd package to the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # Try different possible paths to find the waveshare_epd package
    possible_paths = [
        os.path.join(project_root, "devices", "eink", "waveshare_epd"),
        os.path.join(project_root, "python", "devices", "eink", "waveshare_epd"),
        os.path.join(os.path.dirname(project_root), "devices", "eink", "waveshare_epd"),
        os.path.join(os.path.dirname(project_root), "python", "devices", "eink", "waveshare_epd"),
    ]
    
    waveshare_path = None
    for path in possible_paths:
        if os.path.exists(path):
            waveshare_path = path
            logger.info(f"Found waveshare_epd package at: {path}")
            sys.path.insert(0, os.path.dirname(path))
            break
    
    if not waveshare_path:
        logger.error("Could not find waveshare_epd package. Please check your project structure.")
        sys.exit(1)
    
    # Try to import the package
    try:
        from waveshare_epd import epd3in7
        logger.info("Successfully imported waveshare_epd.epd3in7")
    except ImportError as e:
        logger.error(f"Failed to import waveshare_epd.epd3in7: {e}")
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
        
        # Initialize the display
        epd = epd3in7.EPD()
        logger.info("Initializing display...")
        epd.init(0)  # 0 = 4Gray mode
        epd.Clear(0xFF, 0)
        
        # Draw on the display
        logger.info("Drawing on the display...")
        Himage = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
        draw = ImageDraw.Draw(Himage)
        
        # Draw text
        draw.text((10, 0), 'Hello from Totem!', font=font24, fill=0)
        draw.text((10, 30), '3.7inch E-Ink Test', font=font24, fill=0)
        
        # Draw shapes with different gray levels
        draw.rectangle((10, 70, 150, 110), 'black', 'black')
        draw.text((10, 70), 'Waveshare', font=font36, fill=epd.GRAY1)
        draw.text((10, 120), 'E-Paper', font=font36, fill=epd.GRAY2)
        draw.text((10, 170), 'Demo', font=font36, fill=epd.GRAY3)
        draw.text((10, 220), 'Test', font=font36, fill=epd.GRAY4)
        
        # Draw lines and shapes
        draw.line((180, 50, 230, 100), fill=0)
        draw.line((230, 50, 180, 100), fill=0)
        draw.rectangle((180, 50, 230, 100), outline=0)
        draw.arc((240, 50, 290, 100), 0, 360, fill=0)
        draw.rectangle((300, 50, 350, 100), fill=0)
        
        # Display the image
        logger.info("Displaying image...")
        epd.display_4Gray(epd.getbuffer_4Gray(Himage))
        
        # Wait for 5 seconds
        logger.info("Waiting for 5 seconds...")
        time.sleep(5)
        
        # Show a clock with partial updates
        logger.info("Showing clock with partial updates...")
        epd.init(1)  # 1 = 1Gray mode
        epd.Clear(0xFF, 1)
        
        time_image = Image.new('1', (epd.height, epd.width), 255)
        time_draw = ImageDraw.Draw(time_image)
        
        for i in range(10):  # Show 10 updates
            time_draw.rectangle((10, 10, 120, 50), fill=255)
            time_draw.text((10, 10), time.strftime('%H:%M:%S'), font=font24, fill=0)
            epd.display_1Gray(epd.getbuffer(time_image))
            time.sleep(1)
        
        # Clear the display
        logger.info("Clearing display...")
        epd.init(0)
        epd.Clear(0xFF, 0)
        
        # Put the display to sleep
        logger.info("Putting display to sleep...")
        epd.sleep()
        
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to clean up
        try:
            epd3in7.epdconfig.module_exit(cleanup=True)
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    main() 