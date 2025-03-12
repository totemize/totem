#!/usr/bin/env python3
"""
Test script for Raspberry Pi 5 e-ink display support.
"""
import sys
import os
import time

# Add the parent directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)

from utils.logger import setup_logger, get_logger
try:
    from devices.eink.drivers.waveshare_3in7_pi5 import Driver
    DRIVER_AVAILABLE = True
except ImportError:
    DRIVER_AVAILABLE = False
from PIL import Image, ImageDraw, ImageFont

def main():
    # Set up logging
    setup_logger(level=10)  # DEBUG level
    logger = get_logger()
    
    logger.info("Testing Raspberry Pi 5 e-ink display driver")
    
    try:
        # Try to import gpiod to check if it's available
        try:
            import gpiod
            logger.info("✅ gpiod library is available")
        except ImportError as e:
            logger.error(f"❌ gpiod library is not available: {e}")
            logger.info("Please install gpiod manually: sudo apt install python3-gpiod")
            return
        
        # Try to read cpuinfo
        logger.info("Checking Raspberry Pi version...")
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi 5' in model:
                    logger.info("✅ Detected Raspberry Pi 5")
                else:
                    logger.warning("⚠️ Not running on a Raspberry Pi 5")
        except Exception as e:
            logger.error(f"Failed to check Pi version: {e}")
        
        # Initialize the e-ink display
        if not DRIVER_AVAILABLE:
            logger.error("❌ E-Ink driver not available")
            return
        
        logger.info("Initializing e-ink display driver")
        eink = Driver()
        eink.init()
        
        # Clear the display
        logger.info("Clearing the display")
        eink.clear()
        time.sleep(1)
        
        # Create a test image
        logger.info("Creating test image")
        width = eink.width
        height = eink.height
        image = Image.new('1', (width, height), 255)  # 255: white
        draw = ImageDraw.Draw(image)
        
        # Add text
        try:
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, 24)
            else:
                font = ImageFont.load_default()
        except IOError:
            font = ImageFont.load_default()
        
        draw.text((10, 10), "Raspberry Pi 5", font=font, fill=0)  # 0: black
        draw.text((10, 40), "e-Paper Test", font=font, fill=0)
        draw.text((10, 70), f"Time: {time.strftime('%H:%M:%S')}", font=font, fill=0)
        
        # Draw some shapes
        draw.rectangle((10, 100, width-10, 150), outline=0)
        draw.ellipse((width//2-40, height//2-20, width//2+40, height//2+20), outline=0)
        draw.line((20, height-30, width-20, height-30), fill=0)
        
        # Display the image
        logger.info("Displaying test image")
        eink.display_image(image)
        
        logger.info("Test completed successfully!")
    
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 