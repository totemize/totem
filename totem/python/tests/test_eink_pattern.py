#!/usr/bin/env python3
"""
E-Ink Test Pattern Script
This script displays a high-contrast test pattern on the E-Ink display
to verify that the display is functioning correctly.
"""

import os
import sys
import time
from PIL import Image, ImageDraw
from utils.logger import logger

# Try to import the display manager
try:
    from managers.display_manager import DisplayManager
except ImportError as e:
    print(f"Error importing DisplayManager: {e}")
    sys.exit(1)

def create_test_pattern(width, height):
    """Create a high-contrast test pattern"""
    # Create a white image
    image = Image.new('1', (width, height), 255)  # 255: white
    draw = ImageDraw.Draw(image)
    
    # Draw a black border
    draw.rectangle([(0, 0), (width-1, height-1)], outline=0)
    
    # Draw diagonal lines
    draw.line([(0, 0), (width-1, height-1)], fill=0, width=3)
    draw.line([(0, height-1), (width-1, 0)], fill=0, width=3)
    
    # Draw horizontal and vertical lines
    draw.line([(0, height//2), (width-1, height//2)], fill=0, width=3)
    draw.line([(width//2, 0), (width//2, height-1)], fill=0, width=3)
    
    # Draw some rectangles
    box_size = min(width, height) // 4
    # Top-left
    draw.rectangle([(10, 10), (10+box_size, 10+box_size)], fill=0)
    # Top-right
    draw.rectangle([(width-10-box_size, 10), (width-10, 10+box_size)], fill=0)
    # Bottom-left
    draw.rectangle([(10, height-10-box_size), (10+box_size, height-10)], fill=0)
    # Bottom-right
    draw.rectangle([(width-10-box_size, height-10-box_size), (width-10, height-10)], fill=0)
    
    return image

def main():
    """Main function to display test pattern"""
    logger.info("=== E-Ink Test Pattern Script ===")
    
    # Initialize display manager
    logger.info("Initializing DisplayManager")
    display_manager = DisplayManager()
    
    # Get direct access to the driver
    driver = display_manager.eink_device.driver
    
    # Enable debug mode
    driver.enable_debug_mode(True)
    logger.info("Debug mode enabled")
    
    # Get display dimensions
    width = driver.width
    height = driver.height
    logger.info(f"Display dimensions: {width}x{height}")
    
    # Create test pattern
    logger.info("Creating test pattern")
    image = create_test_pattern(width, height)
    
    # Perform a hardware reset
    logger.info("Performing hardware reset")
    driver.reset()
    time.sleep(1)
    
    # Clear the display
    logger.info("Clearing display")
    driver.clear()
    time.sleep(1)
    
    # Display the test pattern
    logger.info("Displaying test pattern")
    driver.display_image(image)
    
    logger.info("Test pattern displayed. Please check the E-Ink display.")
    logger.info("=== Test Pattern Script Completed ===")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 