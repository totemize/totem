#!/usr/bin/env python3
"""
Test script for the 2.13inch e-Paper HAT
This script demonstrates how to use the 2.13inch e-Paper display.
"""

import os
import sys
import time
from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)

try:
    from utils.logger import logger, setup_logger
    setup_logger(level=10)  # Debug level
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("eink_test")

def is_raspberry_pi():
    """Check if we're running on a Raspberry Pi"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            return 'Raspberry Pi' in model
    except:
        return False

def is_raspberry_pi_5():
    """Check if we're running on a Raspberry Pi 5"""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            return 'Raspberry Pi 5' in model
    except:
        return False

def get_eink_driver():
    """Get the appropriate E-Ink display driver based on hardware"""
    # Check if gpiod is available (required for Pi 5)
    gpiod_available = False
    try:
        import gpiod
        gpiod_available = True
        logger.info("gpiod is available")
    except ImportError:
        logger.warning("gpiod not available")
        logger.info("Please install gpiod manually: sudo apt install python3-gpiod")
    
    # Check which Raspberry Pi model we're running on
    if is_raspberry_pi_5() and gpiod_available:
        logger.info("Detected Raspberry Pi 5, using Pi 5 specific driver")
        from devices.eink.drivers.waveshare_2in13_pi5 import Driver
    elif is_raspberry_pi():
        logger.info("Detected Raspberry Pi (not Pi 5), using standard driver")
        from devices.eink.drivers.waveshare_2in13 import Driver
    else:
        logger.info("Not running on Raspberry Pi, using mock driver")
        # Import the standard driver which will use mock implementations
        from devices.eink.drivers.waveshare_2in13 import Driver
    
    return Driver()

def draw_test_pattern(width, height):
    """Draw a test pattern image"""
    # Create a white background image
    image = Image.new('1', (width, height), 255)  # 255 = white
    draw = ImageDraw.Draw(image)
    
    # Draw a black border
    draw.rectangle([(0, 0), (width-1, height-1)], outline=0)
    
    # Draw horizontal and vertical centerlines
    draw.line([(0, height//2), (width, height//2)], fill=0)
    draw.line([(width//2, 0), (width//2, height)], fill=0)
    
    # Draw diagonal lines
    draw.line([(0, 0), (width, height)], fill=0)
    draw.line([(0, height), (width, 0)], fill=0)
    
    # Draw test text
    try:
        # Try to load a font (DejaVuSans is commonly available on Raspberry Pi)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, 18)
        else:
            # Fall back to PIL's default font
            font = ImageFont.load_default()
    except Exception as e:
        logger.warning(f"Error loading font: {e}")
        font = ImageFont.load_default()
    
    # Add text
    draw.text((width//2, 10), "2.13\" E-Ink", font=font, fill=0, anchor="mt")
    draw.text((width//2, height-10), "Test Pattern", font=font, fill=0, anchor="mb")
    
    return image

def draw_text_screen(width, height, text_lines):
    """Create an image with text content"""
    # Create a white background image
    image = Image.new('1', (width, height), 255)  # 255 = white
    draw = ImageDraw.Draw(image)
    
    # Draw a black border
    draw.rectangle([(0, 0), (width-1, height-1)], outline=0)
    
    try:
        # Try to load a font (DejaVuSans is commonly available on Raspberry Pi)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, 12)
        else:
            # Fall back to PIL's default font
            font = ImageFont.load_default()
    except Exception as e:
        logger.warning(f"Error loading font: {e}")
        font = ImageFont.load_default()
    
    # Add each line of text
    y_position = 10
    line_height = 15
    for line in text_lines:
        draw.text((10, y_position), line, font=font, fill=0)
        y_position += line_height
    
    return image

def main():
    """Main function to test the E-Ink display"""
    print("=== 2.13inch E-Ink Display Test ===")
    
    # Get the driver
    try:
        eink = get_eink_driver()
        eink.init()
        print(f"Display dimensions: {eink.width}x{eink.height}")
    except Exception as e:
        logger.error(f"Failed to initialize E-Ink display: {e}")
        print(f"ERROR: Failed to initialize E-Ink display: {e}")
        return 1
    
    # Test clear
    try:
        print("Clearing display...")
        eink.clear()
        print("Display cleared. Wait for 2 seconds...")
        time.sleep(2)
    except Exception as e:
        logger.error(f"Failed to clear display: {e}")
        print(f"ERROR: Failed to clear display: {e}")
        return 1
    
    # Test pattern
    try:
        print("Displaying test pattern...")
        test_image = draw_test_pattern(eink.width, eink.height)
        eink.display_image(test_image)
        print("Test pattern displayed. Wait for 5 seconds...")
        time.sleep(5)
    except Exception as e:
        logger.error(f"Failed to display test pattern: {e}")
        print(f"ERROR: Failed to display test pattern: {e}")
        return 1
    
    # Text display
    try:
        print("Displaying text screen...")
        text_lines = [
            "Waveshare 2.13\" E-Ink",
            "250x122 pixels",
            f"Model: {'Pi 5' if is_raspberry_pi_5() else 'Standard'}",
            f"Time: {time.strftime('%H:%M:%S')}",
            f"Date: {time.strftime('%Y-%m-%d')}",
            "Test successful!"
        ]
        text_image = draw_text_screen(eink.width, eink.height, text_lines)
        eink.display_image(text_image)
        print("Text screen displayed.")
    except Exception as e:
        logger.error(f"Failed to display text screen: {e}")
        print(f"ERROR: Failed to display text screen: {e}")
        return 1
    
    # Sleep mode
    try:
        print("Putting display to sleep...")
        eink.sleep()
        print("Display is now in sleep mode.")
    except Exception as e:
        logger.error(f"Failed to put display to sleep: {e}")
        print(f"WARNING: Failed to put display to sleep: {e}")
    
    print("Test completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 