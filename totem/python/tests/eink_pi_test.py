#!/usr/bin/env python3
"""
E-Ink Pi Test

Tests the E-Ink display on a Raspberry Pi using the consolidated driver.
Uses 4Gray mode like the manufacturer's example shows works well.
"""

import os
import sys
import time
import logging
import argparse

# Add the parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eink_pi_test")

def run_test():
    """Run the E-Ink display test"""
    try:
        # Import the driver - use a direct import since we're in the totem dir
        from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
        
        logger.info("Initializing E-Ink display")
        epd = WaveshareEPD3in7()
        
        # Print display configuration
        logger.info(f"E-Ink Display Configuration:")
        logger.info(f"  Mock mode: {epd.mock_mode}")
        logger.info(f"  NVME compatible: {epd.nvme_compatible}")
        logger.info(f"  Software SPI: {epd.using_sw_spi}")
        logger.info(f"  Width x Height: {epd.width} x {epd.height}")
        
        # Initialize with 4Gray mode like manufacturer's example
        logger.info("Initializing display in 4Gray mode")
        epd.init(0)  # 0 = 4Gray mode
        
        # Clear the display
        logger.info("Clearing display")
        epd.Clear(0xFF, 0)  # White (0xFF) in 4Gray mode
        time.sleep(1)
        
        # Display text using the display_text method
        logger.info("Displaying test text")
        epd.display_text("Consolidated Driver", 10, 10, 36)
        epd.display_text("4Gray Mode Test", 10, 60, 24)
        time.sleep(3)  # Give time to see the display
        
        # Try advanced functionality with PIL if available
        try:
            from PIL import Image, ImageDraw, ImageFont
            logger.info("PIL available, testing advanced graphics")
            
            # Create a test image
            image = Image.new('L', (epd.height, epd.width), 255)  # Use Landscape orientation like manufacturer
            draw = ImageDraw.Draw(image)
            
            # Get a font
            font = None
            try:
                # Try common font locations on Raspberry Pi
                font_paths = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/TTF/DejaVuSans.ttf'
                ]
                
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, 24)
                        break
                        
                if font is None:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Draw grayscale showcases
            draw.text((10, 10), "Grayscale Test", font=font, fill=0)
            
            # Draw examples of the 4 grayscale levels
            draw.text((10, 50), "Black (GRAY1)", font=font, fill=epd.GRAY1)
            draw.text((10, 80), "Dark Gray (GRAY2)", font=font, fill=epd.GRAY2)
            draw.text((10, 110), "Light Gray (GRAY3)", font=font, fill=epd.GRAY3)
            draw.text((10, 140), "White (GRAY4)", font=font, fill=epd.GRAY4)
            
            # Draw some shapes to demonstrate graphics
            draw.line((10, 180, 100, 240), fill=0, width=2)
            draw.rectangle((120, 180, 220, 240), outline=0)
            
            # Display the grayscale image
            logger.info("Displaying grayscale test image")
            epd.display_4Gray(epd.getbuffer_4Gray(image))
            time.sleep(5)  # Give time to see the display
            
        except ImportError:
            logger.warning("PIL not available, skipping advanced graphics test")
        
        # Final success screen
        logger.info("Displaying success message")
        epd.Clear(0xFF, 0)
        epd.display_text("Test Complete", 10, 10, 36)
        epd.display_text("SUCCESS!", 10, 60, 36)
        
        # Sleep the display to save power
        logger.info("Putting display to sleep")
        epd.sleep()
        
        logger.info("Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during E-Ink display test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='E-Ink Pi Test')
    parser.add_argument('--mock', action='store_true', help='Use mock mode (no hardware)')
    parser.add_argument('--nvme', action='store_true', help='Use NVME compatibility mode')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Set environment variables
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
        logger.info("Using mock mode for display operations")
    
    if args.nvme:
        os.environ['NVME_COMPATIBLE'] = '1'
        logger.info("Using NVME compatibility mode")
    
    # Set busy timeout to be longer than default
    os.environ['EINK_BUSY_TIMEOUT'] = '10'
    
    # Run the test
    success = run_test()
    
    # Return exit code
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 