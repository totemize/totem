#!/usr/bin/env python3
"""
EInk Display Test Script Using Manufacturer's Approach

This script emulates the manufacturer's example but with our NVME compatibility settings.
It's designed to help debug why the manufacturer's script works but ours doesn't.

Usage:
  python3 eink_emulate_manufacturer.py
  python3 eink_emulate_manufacturer.py --nvme
  python3 eink_emulate_manufacturer.py --mock
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Add the parent directory to the path
script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent.parent
sys.path.insert(0, str(project_dir))

def run_test(nvme_compatible=False, mock_mode=False, busy_timeout=10):
    """Run the EInk display test using an approach similar to the manufacturer's example"""
    # Set environment variables
    if nvme_compatible:
        os.environ['NVME_COMPATIBLE'] = '1'
    if mock_mode:
        os.environ['EINK_MOCK_MODE'] = '1'
    
    # Set busy timeout
    os.environ['EINK_BUSY_TIMEOUT'] = str(busy_timeout)
    
    # Check if the waveshare_epd module is available (manufacturer's module)
    manufacturer_module_available = False
    try:
        # First try the manufacturer's module
        from waveshare_epd import epd3in7
        manufacturer_module_available = True
        print("Using manufacturer's waveshare_epd module")
    except ImportError:
        print("Manufacturer's waveshare_epd module not found")
    
    try:
        if manufacturer_module_available:
            # Use the manufacturer's module
            epd = epd3in7.EPD()
            logging.info("Initializing display (manufacturer's module)")
            epd.init(0)  # 0 = 4-Gray mode
            epd.Clear(0xFF, 0)
            
            # Get font
            from PIL import Image, ImageDraw, ImageFont
            font36 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
            
            # Create test image
            logging.info("Creating test image")
            Himage = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
            draw = ImageDraw.Draw(Himage)
            
            # Draw text
            message = "Hello Totem!\nUsing manufacturer's\nmodule - NVME " + ("compatible" if nvme_compatible else "standard")
            lines = message.split('\n')
            y_position = 10
            for line in lines:
                draw.text((10, y_position), line, font=font36, fill=0)
                y_position += 50
            
            # Display the image
            logging.info("Displaying image")
            epd.display_4Gray(epd.getbuffer_4Gray(Himage))
            
            # Sleep
            time.sleep(3)
            
            # Sleep mode
            logging.info("Sleep mode")
            epd.sleep()
            
        else:
            # Use our custom module with manufacturer-like approach
            from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7, RST_PIN, DC_PIN, CS_PIN, BUSY_PIN
            
            epd = WaveshareEPD3in7()
            
            # Print configuration
            print(f"EInk Display Configuration:")
            print(f"  Mock mode: {epd.mock_mode}")
            print(f"  NVME compatible: {epd.nvme_compatible}")
            print(f"  Software SPI: {epd.using_sw_spi}")
            print(f"  Busy timeout: {busy_timeout} seconds")
            print(f"  RST_PIN: {RST_PIN}")
            print(f"  DC_PIN: {DC_PIN}")
            print(f"  CS_PIN: {CS_PIN}")
            print(f"  BUSY_PIN: {BUSY_PIN}")
            
            # Initialize the display with explicit mode
            print("Initializing display (our custom module)")
            epd.init(mode=0)  # Try explicit 4-gray mode like manufacturer
            epd.Clear(clear_color=0xFF, mode=0)  # Try explicit params like manufacturer
            
            # Create and display image more similar to manufacturer's approach
            from PIL import Image, ImageDraw, ImageFont
            try:
                font36 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
            except:
                font36 = None
                print("Font not found, using default")
            
            width = epd.width
            height = epd.height
            
            # Create image (rotated like manufacturer example)
            print("Creating image")
            image = Image.new('L', (height, width), 0xFF)  # 0xFF = white
            draw = ImageDraw.Draw(image)
            
            # Add text
            message = "Hello Totem!\nUsing our module\nwith manufacturer\napproach - NVME " + ("compatible" if nvme_compatible else "standard")
            lines = message.split('\n')
            y_position = 10
            for line in lines:
                draw.text((10, y_position), line, font=font36, fill=0)
                y_position += 50
            
            # Display the image
            print("Displaying image")
            if hasattr(epd, 'getbuffer_4Gray') and hasattr(epd, 'display_4Gray'):
                # Use manufacturer-like methods if available
                buffer = epd.getbuffer_4Gray(image)
                epd.display_4Gray(buffer)
            else:
                # Fallback to our custom method
                buffer = epd.getbuffer(image)
                epd.display(buffer)
            
            # Sleep
            time.sleep(3)
            
            # Sleep mode
            print("Putting display to sleep")
            epd.sleep()
            
            # Cleanup
            print("Cleaning up")
            epd.close()
        
        print("\nTest completed successfully!")
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Test EInk display using manufacturer approach')
    parser.add_argument('--nvme', action='store_true', 
                        help='Enable NVME compatibility mode')
    parser.add_argument('--mock', action='store_true', 
                        help='Run in mock mode without physical display')
    parser.add_argument('--timeout', type=int, default=10,
                        help='Busy timeout in seconds (default: 10)')
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"EInk Manufacturer-Style Test")
    print(f"----------------------------")
    print(f"NVME compatibility: {'Enabled' if args.nvme else 'Disabled'}")
    print(f"Mock mode: {'Enabled' if args.mock else 'Disabled'}")
    print(f"Busy timeout: {args.timeout} seconds")
    print(f"----------------------------\n")
    
    return run_test(args.nvme, args.mock, args.timeout)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 