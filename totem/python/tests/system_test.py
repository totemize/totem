import argparse
import logging
import os
import sys
import time

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Configure the logger
from utils.logger import logger

# Try to import PIL
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.error("PIL/Pillow package not installed. Please install with: pip install Pillow")

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run E-Ink display test following manufacturer approach')
parser.add_argument('--mock', action='store_true', help='Use mock mode (no hardware)')
parser.add_argument('--nvme', action='store_true', help='Use NVME compatibility mode')
parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
args = parser.parse_args()

def run_eink_test(args):
    """Test the E-Ink display functionality using the manufacturer's approach"""
    logger.info("Starting E-Ink display test with manufacturer-like approach")
    
    # Check if PIL is available
    if not PIL_AVAILABLE:
        logger.error("Cannot run test: PIL/Pillow package is required")
        logger.error("Please install with: pip install Pillow")
        return False
    
    # Set environment variables based on args
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
        logger.info("Using mock mode for display operations")
    
    if args.nvme:
        os.environ['NVME_COMPATIBLE'] = '1'
        logger.info("Using NVME compatibility mode")
        
    # Set busy timeout 
    os.environ['EINK_BUSY_TIMEOUT'] = '10'
    
    try:
        # Import directly from the drivers directory
        from python.devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
        
        # Initialize the display
        logger.info("Initializing E-Ink display")
        epd = WaveshareEPD3in7()
        
        # Print configuration
        logger.info(f"E-Ink Display Configuration:")
        logger.info(f"  Mock mode: {epd.mock_mode}")
        logger.info(f"  NVME compatible: {epd.nvme_compatible}")
        logger.info(f"  Software SPI: {epd.using_sw_spi}")
        
        # Initialize with 4Gray mode (like manufacturer example)
        logger.info("Initializing display in 4Gray mode")
        epd.init(0)  # 0 = 4Gray mode
        
        # Clear the display
        logger.info("Clearing display")
        epd.Clear(0xFF, 0)  # Clear with white (0xFF) in 4Gray mode
        
        # Try to load a font
        font = None
        font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        try:
            # Check if the font exists
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, 36)
            else:
                # Try other common font locations
                font_paths = [
                    '/usr/share/fonts/TTF/DejaVuSans.ttf',              
                    '/usr/share/fonts/dejavu/DejaVuSans.ttf',           
                    '/System/Library/Fonts/Helvetica.ttc',               
                    'C:\\Windows\\Fonts\\Arial.ttf'                     
                ]
                
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, 36)
                        logger.info(f"Using font: {path}")
                        break
                        
            if font is None:
                logger.warning("No TrueType fonts found, using default")
                font = ImageFont.load_default()
        except Exception as e:
            logger.error(f"Error loading font: {e}")
            font = ImageFont.load_default()
        
        # Create a new image with the display dimensions (rotated like manufacturer example)
        logger.info("Creating test image")
        image = Image.new('L', (epd.height, epd.width), 255)  # 'L' = 8-bit grayscale, 255 = white
        draw = ImageDraw.Draw(image)
        
        # Draw some text and shapes
        logger.info("Drawing on image")
        draw.text((10, 10), 'System Test', font=font, fill=0)
        draw.text((10, 50), 'Totem 3.7\" E-Ink', font=font, fill=0)
        
        # Draw lines
        draw.line((10, 100, 150, 200), fill=0)
        draw.line((150, 100, 10, 200), fill=0)
        
        # Draw rectangle
        draw.rectangle((200, 100, 300, 200), outline=0)
        
        # Display the image using 4Gray mode
        logger.info("Displaying image using 4Gray mode")
        epd.display_4Gray(epd.getbuffer_4Gray(image))
        
        # Wait a moment
        time.sleep(5)
        
        # Show a second screen with grayscale levels
        logger.info("Creating grayscale test image")
        gray_image = Image.new('L', (epd.height, epd.width), 255)
        draw = ImageDraw.Draw(gray_image)
        
        # Draw grayscale text showing different gray levels
        draw.text((10, 10), 'Grayscale Test', font=font, fill=0)
        
        # Use the constants from the driver for grayscale
        draw.text((10, 60), 'Black (GRAY1)', font=font, fill=epd.GRAY1)
        draw.text((10, 100), 'Dark Gray (GRAY2)', font=font, fill=epd.GRAY2)
        draw.text((10, 140), 'Light Gray (GRAY3)', font=font, fill=epd.GRAY3)
        draw.text((10, 180), 'White (GRAY4)', font=font, fill=epd.GRAY4)
        
        # Display grayscale image
        logger.info("Displaying grayscale test")
        epd.display_4Gray(epd.getbuffer_4Gray(gray_image))
        
        # Wait a moment
        time.sleep(5)
        
        # Final success screen
        logger.info("Creating success screen")
        final_image = Image.new('L', (epd.height, epd.width), 255)
        draw = ImageDraw.Draw(final_image)
        draw.text((50, 80), 'Test Complete', font=font, fill=0)
        draw.text((50, 140), 'SUCCESS!', font=font, fill=0)
        
        # Display final image
        logger.info("Displaying success screen")
        epd.display_4Gray(epd.getbuffer_4Gray(final_image))
        
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
    """Main function to run the system test"""
    # Configure logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Run the E-Ink test
    success = run_eink_test(args)
    
    # Display result
    if success:
        logger.info("System test completed successfully")
        return 0
    else:
        logger.error("System test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 