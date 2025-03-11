#!/usr/bin/env python3
"""
E-Ink Debug Test Script
This script tests the enhanced E-Ink driver with debug mode, explicit reset sequence,
and GPIO control testing to diagnose display issues.
"""

import os
import sys
import time
from utils.logger import logger
from managers.display_manager import DisplayManager
from PIL import Image, ImageDraw, ImageFont
import argparse
import logging

# Setup logging based on environment variable
log_level_str = os.environ.get('TOTEM_LOG_LEVEL', 'INFO')
try:
    log_level = getattr(logging, log_level_str.upper())
except AttributeError:
    log_level = logging.INFO

# Configure root logger
logging.basicConfig(level=log_level, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_basic_gpio():
    """Test basic GPIO control to verify driver functionality"""
    logger.info("=== Testing Basic GPIO Control ===")
    
    # Initialize display manager with default driver
    display_manager = DisplayManager()
    
    # Get direct access to the driver
    driver = display_manager.eink_device.driver
    
    # Run GPIO test
    if driver.test_gpio_control():
        logger.info("✅ GPIO test successful")
        return True
    else:
        logger.error("❌ GPIO test failed")
        return False

def test_enhanced_reset():
    """Test the enhanced reset sequence"""
    logger.info("=== Testing Enhanced Reset Sequence ===")
    
    # Initialize display manager with default driver
    display_manager = DisplayManager()
    
    # Get direct access to the driver
    driver = display_manager.eink_device.driver
    
    # Enable debug mode
    driver.enable_debug_mode(True)
    
    try:
        # Perform reset
        logger.info("Performing enhanced reset sequence...")
        driver.reset()
        
        # Wait for a moment
        time.sleep(1)
        
        # Try to clear the display
        logger.info("Clearing display after reset...")
        driver.clear()
        
        logger.info("✅ Enhanced reset sequence completed")
        return True
    except Exception as e:
        logger.error(f"❌ Reset sequence failed: {e}")
        return False

def test_debug_display():
    """Test display with debug mode enabled"""
    logger.info("=== Testing Display with Debug Mode ===")
    
    # Initialize display manager with default driver
    display_manager = DisplayManager()
    
    # Get direct access to the driver
    driver = display_manager.eink_device.driver
    
    # Enable debug mode
    driver.enable_debug_mode(True)
    
    try:
        # Create a test image
        image = Image.new('1', (driver.width, driver.height), 255)  # 255: white
        draw = ImageDraw.Draw(image)
        
        # Draw a black rectangle border
        draw.rectangle([(0, 0), (driver.width-1, driver.height-1)], outline=0)
        
        # Draw some text
        font_size = 24
        try:
            font = ImageFont.truetype("FreeSans.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
        
        # Draw centered test text
        text = "E-Ink Debug Test"
        text_width, text_height = draw.textsize(text, font=font) if hasattr(draw, 'textsize') else font.getbbox(text)[2:4]
        position = ((driver.width - text_width) // 2, (driver.height - text_height) // 2)
        draw.text(position, text, font=font, fill=0)  # 0: black
        
        # Display the image
        logger.info("Displaying test pattern...")
        driver.display_image(image)
        
        logger.info("✅ Display test completed with debug mode")
        return True
    except Exception as e:
        logger.error(f"❌ Display test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='E-Ink Debug Test Script')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--gpio', action='store_true', help='Test basic GPIO control')
    parser.add_argument('--reset', action='store_true', help='Test enhanced reset sequence')
    parser.add_argument('--display', action='store_true', help='Test display with debug mode')
    
    args = parser.parse_args()
    
    # If no specific test is selected, run all tests
    if not (args.gpio or args.reset or args.display or args.all):
        args.all = True
    
    results = []
    
    if args.gpio or args.all:
        results.append(("GPIO Test", test_basic_gpio()))
    
    if args.reset or args.all:
        results.append(("Reset Test", test_enhanced_reset()))
    
    if args.display or args.all:
        results.append(("Display Test", test_debug_display()))
    
    # Print summary
    logger.info("\n=== Test Results ===")
    for name, result in results:
        logger.info(f"{name}: {'✅ PASSED' if result else '❌ FAILED'}")
    
    # Overall result
    if all(result for _, result in results):
        logger.info("\n✅ All tests passed successfully!")
        return 0
    else:
        logger.error("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 