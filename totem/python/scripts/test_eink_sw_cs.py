#!/usr/bin/env python3
"""
Test script for the 2.13inch e-Paper HAT with Software CS
This script demonstrates how to use the 2.13inch e-Paper display with software CS control.
"""

import os
import sys
import time
import argparse
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
    logger = logging.getLogger("eink_sw_cs_test")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Test the E-Ink display with software CS control')
    parser.add_argument('-a', '--alt-pins', action='store_true', help='Use alternative pins for the display')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode for detailed logging')
    parser.add_argument('-s', '--spi-device', type=int, default=0, help='SPI device number (default: 0)')
    parser.add_argument('-b', '--spi-bus', type=int, default=0, help='SPI bus number (default: 0)')
    
    return parser.parse_args()

def set_pin_environment(args):
    """Set environment variables for pin configuration"""
    if args.alt_pins:
        logger.info("Using alternative pins for E-Ink display")
        os.environ['USE_ALT_EINK_PINS'] = '1'
        os.environ['EINK_RST_PIN'] = '27'
        os.environ['EINK_DC_PIN'] = '22'
        os.environ['EINK_BUSY_PIN'] = '23'
        os.environ['EINK_CS_PIN'] = '7'
    
    # Set SPI bus and device
    os.environ['EINK_SPI_BUS'] = str(args.spi_bus)
    os.environ['EINK_SPI_DEVICE'] = str(args.spi_device)
    
    logger.info(f"Using SPI bus {args.spi_bus}, device {args.spi_device}")

def get_sw_cs_driver():
    """Get the E-Ink display driver with software CS control"""
    try:
        from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
        logger.info("Successfully imported software CS driver")
        return Driver()
    except ImportError as e:
        logger.error(f"Failed to import software CS driver: {e}")
        logger.error("Make sure the waveshare_2in13_pi5_sw_cs.py file exists in the drivers directory")
        return None

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
    draw.text((width//2, 10), "E-Ink SW CS", font=font, fill=0, anchor="mt")
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
    """Main function to test the E-Ink display with software CS"""
    print("=== 2.13inch E-Ink Display Test with Software CS ===")
    
    # Parse command line arguments
    args = parse_args()
    
    # Set environment variables for pin configuration
    set_pin_environment(args)
    
    # Get the driver
    eink = get_sw_cs_driver()
    if eink is None:
        return 1
    
    # Enable debug mode if requested
    if args.debug:
        eink.enable_debug_mode(True)
    
    # Initialize the display
    try:
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
        # Get pin configuration
        rst_pin = os.environ.get('EINK_RST_PIN', '17')
        dc_pin = os.environ.get('EINK_DC_PIN', '25')
        busy_pin = os.environ.get('EINK_BUSY_PIN', '24')
        cs_pin = os.environ.get('EINK_CS_PIN', '8')
        
        text_lines = [
            "2.13\" E-Ink SW CS",
            "250x122 pixels",
            f"SPI: {args.spi_bus}.{args.spi_device}",
            f"Pins: RST={rst_pin}, DC={dc_pin}",
            f"    BUSY={busy_pin}, CS={cs_pin}",
            f"Time: {time.strftime('%H:%M:%S')}",
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