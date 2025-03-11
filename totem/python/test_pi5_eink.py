#!/usr/bin/env python3
"""
Test script for Raspberry Pi 5 e-ink display support.
"""
import sys
import time
from utils.logger import setup_logger, get_logger
from devices.eink.eink import EInk
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
            logger.info("Installing gpiod using pip...")
            try:
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "gpiod"], check=True)
                logger.info("gpiod installed successfully, please restart the script")
                return
            except Exception as e:
                logger.error(f"Failed to install gpiod: {e}")
                logger.info("Please install gpiod manually: sudo apt install python3-gpiod")
                return
        
        # Try to read cpuinfo
        logger.info("Checking Raspberry Pi version...")
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                if 'Raspberry Pi 5' in cpuinfo:
                    logger.info("✅ Detected Raspberry Pi 5")
                else:
                    logger.warning("⚠️ Not running on a Raspberry Pi 5")
        except Exception as e:
            logger.error(f"Failed to check Pi version: {e}")
        
        # Initialize the e-ink display
        logger.info("Initializing e-ink display with automatic driver detection")
        eink = EInk()  # Let it auto-detect the hardware
        eink.initialize()
        
        # Clear the display
        logger.info("Clearing the display")
        eink.clear_display()
        time.sleep(1)
        
        # Create a test image
        logger.info("Creating test image")
        width = eink.driver.width
        height = eink.driver.height
        image = Image.new('1', (width, height), 255)  # 255: white
        draw = ImageDraw.Draw(image)
        
        # Add text
        try:
            font = ImageFont.truetype("FreeSans.ttf", 24)
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