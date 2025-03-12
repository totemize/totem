#!/usr/bin/env python3
"""
E-Ink Quick Test Script
This script performs a simple test of the E-Ink display to verify it's working correctly.
"""

import os
import sys
import time
import traceback

# Configure path to include the totem modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, project_root)

try:
    from utils.logger import logger, setup_logger
    setup_logger(level=10)  # Debug level
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("eink_test")

def test_eink_display():
    """Test the E-Ink display with a simple pattern"""
    try:
        # Try to import dependencies
        try:
            import spidev
            logger.info(f"spidev module imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import spidev: {e}")
            print("ERROR: The spidev module is not installed.")
            print("Please run fix_eink_dependencies.sh first.")
            return False
            
        # Try to import PIL
        try:
            from PIL import Image, ImageDraw, ImageFont
            logger.info("PIL modules imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import PIL: {e}")
            print("ERROR: The PIL/Pillow module is not installed.")
            print("Please run fix_eink_dependencies.sh first.")
            return False
            
        # Import the E-Ink device
        try:
            from devices.eink.eink import EInk
            logger.info("EInk module imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import EInk module: {e}")
            print("ERROR: Could not import the EInk module.")
            return False
        
        # Initialize E-Ink display
        eink = None
        try:
            logger.info("Initializing E-Ink display with waveshare_3in7_pi5 driver")
            eink = EInk("waveshare_3in7_pi5")
            eink.initialize()
            logger.info("E-Ink display initialized successfully")
            print("E-Ink display initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize E-Ink display: {e}")
            logger.error(traceback.format_exc())
            print(f"ERROR: Failed to initialize E-Ink display: {e}")
            return False
        
        # Clear the display
        try:
            logger.info("Clearing display")
            eink.clear_display()
            logger.info("Display cleared")
            print("Display cleared. Screen should be white (or black depending on the model).")
            time.sleep(2)  # Wait for display to update
        except Exception as e:
            logger.error(f"Failed to clear display: {e}")
            print(f"ERROR: Failed to clear display: {e}")
            return False
        
        # Create a test image
        try:
            logger.info("Creating test image")
            width = eink.driver.width
            height = eink.driver.height
            logger.info(f"Display dimensions: {width}x{height}")
            
            # Create a white background image
            image = Image.new('1', (width, height), 255)  # 255 = white, 0 = black
            draw = ImageDraw.Draw(image)
            
            # Draw a black border
            draw.rectangle([(0, 0), (width-1, height-1)], outline=0)
            
            # Draw diagonal lines
            draw.line([(0, 0), (width-1, height-1)], fill=0, width=3)
            draw.line([(0, height-1), (width-1, 0)], fill=0, width=3)
            
            # Draw a text label
            message = "E-Ink Test Successful!"
            font_size = height // 20
            try:
                # Try to load a system font
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
                ]
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
                
                if font is None:
                    # Fall back to default font
                    font = ImageFont.load_default()
            except Exception:
                # Fall back to default font
                font = ImageFont.load_default()
            
            # Calculate text position for center of the screen
            text_width, text_height = draw.textbbox((0, 0), message, font=font)[2:4]
            text_x = (width - text_width) // 2
            text_y = (height - text_height) // 2
            
            # Draw text
            draw.text((text_x, text_y), message, font=font, fill=0)
            
            # Add a timestamp
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            timestamp_message = f"Test: {timestamp}"
            draw.text((10, height - 20), timestamp_message, font=font, fill=0)
            
            logger.info("Test image created")
        except Exception as e:
            logger.error(f"Failed to create test image: {e}")
            print(f"ERROR: Failed to create test image: {e}")
            return False
        
        # Display the test image
        try:
            logger.info("Displaying test image")
            eink.display_image(image)
            logger.info("Test image displayed")
            print("Test image displayed successfully.")
            print("You should see a rectangular border, diagonal lines, and text on the display.")
        except Exception as e:
            logger.error(f"Failed to display test image: {e}")
            print(f"ERROR: Failed to display test image: {e}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Unexpected error in test_eink_display: {e}")
        logger.error(traceback.format_exc())
        print(f"ERROR: Unexpected error: {e}")
        return False

def main():
    """Main function to run the E-Ink display test"""
    print("=== E-INK DISPLAY QUICK TEST ===")
    print("This script will test if the E-Ink display is working correctly.")
    
    result = test_eink_display()
    
    if result:
        print("\n✅ E-Ink display test PASSED!")
        print("If you can see the test pattern on the display, everything is working correctly.")
        print("The driver and all dependencies are properly installed.")
    else:
        print("\n❌ E-Ink display test FAILED!")
        print("Please check the error messages above.")
        print("You may need to run fix_eink_dependencies.sh to fix issues with the E-Ink display.")
        print("  sudo python/scripts/fix_eink_dependencies.sh")
    
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main()) 