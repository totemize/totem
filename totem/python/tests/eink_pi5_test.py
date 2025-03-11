#!/usr/bin/env python3
"""
E-Ink Pi5 Test Script
This script tests the Waveshare 3.7in E-Ink display on Raspberry Pi 5
with the updated driver supporting both gpiod v1 and v2 APIs.
"""

import os
import sys
import time
import logging
from PIL import Image, ImageDraw, ImageFont
import argparse

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("eink_pi5_test")

def test_device_init():
    """Test device initialization"""
    logger.info("=== Testing E-Ink Device Initialization ===")
    
    try:
        from devices.eink.eink import EInk
        
        logger.info("Creating EInk instance...")
        display = EInk(force_driver='waveshare_3in7_pi5')
        logger.info(f"Display initialized, driver: {display.driver.__class__.__name__}")
        
        # Check if hardware mode is enabled
        if hasattr(display.driver, 'USE_HARDWARE'):
            logger.info(f"Hardware mode: {'ENABLED' if display.driver.USE_HARDWARE else 'DISABLED (mock mode)'}")
        
        # Enable debug mode
        if hasattr(display.driver, 'enable_debug_mode'):
            display.driver.enable_debug_mode(True)
            logger.info("Debug mode enabled")
        
        return display
    except Exception as e:
        logger.error(f"Error initializing device: {e}")
        logger.exception("Traceback:")
        return None

def test_display(eink):
    """Test display functionality"""
    logger.info("=== Testing E-Ink Display ===")
    
    if eink is None:
        logger.error("Display not initialized, skipping test")
        return False
    
    try:
        # Clear the display
        logger.info("Clearing display...")
        eink.clear()
        time.sleep(1)
        
        # Create a test image
        logger.info("Creating test image...")
        image = Image.new('1', (eink.width, eink.height), 255)  # 255: white
        draw = ImageDraw.Draw(image)
        
        # Add a border
        draw.rectangle([(0, 0), (eink.width-1, eink.height-1)], outline=0)
        
        # Draw some text
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 24)
        except IOError:
            font = ImageFont.load_default()
            
        draw.text((10, 10), "E-Ink Display Test", font=font, fill=0)
        draw.text((10, 40), "Pi 5 gpiod Driver", font=font, fill=0)
        draw.text((10, 70), time.strftime("%Y-%m-%d %H:%M:%S"), font=font, fill=0)
        
        # Draw test patterns
        # Horizontal lines
        for y in range(100, 180, 10):
            draw.line([(10, y), (eink.width-10, y)], fill=0, width=1)
        
        # Vertical lines
        for x in range(50, eink.width-50, 50):
            draw.line([(x, 100), (x, 170)], fill=0, width=1)
        
        # Draw circles
        for r in range(10, 40, 10):
            draw.ellipse([(eink.width//2-r, 200-r), (eink.width//2+r, 200+r)], outline=0)
        
        # Display the image
        logger.info("Displaying test image...")
        eink.display(image)
        logger.info("Test image displayed successfully")
        
        return True
    except Exception as e:
        logger.error(f"Error during display test: {e}")
        logger.exception("Traceback:")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test E-Ink display on Raspberry Pi 5")
    parser.add_argument('--gpio-debug', action='store_true', help='Run GPIO debug test first')
    args = parser.parse_args()
    
    logger.info("=== Starting E-Ink Pi5 Test ===")
    
    # Run GPIO debug test if requested
    if args.gpio_debug:
        logger.info("Running GPIO debug test...")
        from tests.eink_gpio_debug import main as gpio_debug
        gpio_debug()
    
    # Initialize device
    eink = test_device_init()
    
    # Test display
    if eink:
        test_display(eink)
    
    logger.info("=== E-Ink Pi5 Test Complete ===")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 