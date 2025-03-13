#!/usr/bin/env python3
"""
EInk Message Display Script

A simple script to display messages on the EInk display.
Works in both NVME-compatible mode and regular mode.
Uses the manufacturer's approach with 4Gray mode.

Usage:
  python3 eink_message.py "Your message here"
  python3 eink_message.py --nvme "Message with NVME compatibility"
  python3 eink_message.py --mock "Test in mock mode"
  python3 eink_message.py --timeout 20 "Increase busy timeout to 20 seconds"
  python3 eink_message.py --help
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add the parent directory to the path
script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent.parent
sys.path.insert(0, str(project_dir))

def display_message(message, nvme_compatible=False, mock_mode=False, font_size=36, busy_timeout=10):
    """Display a message on the EInk display using manufacturer's approach"""
    # Set environment variables
    if nvme_compatible:
        os.environ['NVME_COMPATIBLE'] = '1'
    if mock_mode:
        os.environ['EINK_MOCK_MODE'] = '1'
    
    # Set busy timeout
    os.environ['EINK_BUSY_TIMEOUT'] = str(busy_timeout)
    
    # Import the EInk driver
    from python.devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7, RST_PIN, DC_PIN, CS_PIN, BUSY_PIN
    from python.devices.eink.drivers.waveshare_3in7 import MOSI_PIN, SCK_PIN
    logger.info("Imported from python.devices.eink.drivers.waveshare_3in7")

    try:
        # Initialize the display
        print("Initializing display...")
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
        if epd.using_sw_spi:
            print(f"  MOSI_PIN: {MOSI_PIN}")
            print(f"  SCK_PIN: {SCK_PIN}")
        
        # Initialize the display in 4Gray mode (like manufacturer example)
        epd.init(0)  # 0 = 4Gray mode
        print("Display initialized")
        
        # Clear the display
        print("Clearing display...")
        epd.Clear(0xFF, 0)  # Clear with white (0xFF) in 4Gray mode
        print("Display cleared")
        
        # Replace escaped newlines with actual newlines
        if '\\n' in message:
            message = message.replace('\\n', '\n')
        
        # Create a new image with the display dimensions (rotated like manufacturer example)
        print("Creating image...")
        image = Image.new('L', (epd.height, epd.width), 255)  # 'L' = 8-bit grayscale, 255 = white
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        font = None
        try:
            # Try common system font paths
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                '/usr/share/fonts/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                'C:\\Windows\\Fonts\\Arial.ttf'
            ]
            
            for path in font_paths:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, font_size)
                    print(f"Using font: {path}")
                    break
                    
            if font is None:
                print("No TrueType fonts found, using default")
                font = ImageFont.load_default()
        except Exception as e:
            print(f"Error loading font: {e}")
            font = ImageFont.load_default()
        
        # Draw the message
        print("Drawing message:")
        print(message)
        lines = message.split('\n')
        y_position = 10
        for line in lines:
            print(f"Drawing line at y={y_position}: {line}")
            draw.text((10, y_position), line, font=font, fill=0)  # 0 = black
            y_position += int(font_size * 1.5)  # Space lines based on font size
        
        # Display the image using 4Gray mode (like manufacturer example)
        print("Displaying image...")
        epd.display_4Gray(epd.getbuffer_4Gray(image))
        
        # Sleep the display to save power
        print("Putting display to sleep...")
        epd.sleep()
        
        # Clean up
        print("Cleaning up resources...")
        epd.close()
        
        print("\nMessage successfully displayed on EInk display!")
        return True
    except Exception as e:
        print(f"Error displaying message: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Display a message on the EInk display')
    parser.add_argument('message', nargs='?', default="Hello Totem!\nEInk Display\nTest", 
                        help='Message to display (use \\n for new lines)')
    parser.add_argument('--nvme', action='store_true', 
                        help='Enable NVME compatibility mode')
    parser.add_argument('--mock', action='store_true', 
                        help='Run in mock mode without physical display')
    parser.add_argument('--font-size', type=int, default=36,
                        help='Font size for the message (default: 36)')
    parser.add_argument('--timeout', type=int, default=10,
                        help='Busy timeout in seconds (default: 10)')
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"EInk Message Display")
    print(f"-------------------")
    print(f"Message: {args.message}")
    print(f"NVME compatibility: {'Enabled' if args.nvme else 'Disabled'}")
    print(f"Mock mode: {'Enabled' if args.mock else 'Disabled'}")
    print(f"Font size: {args.font_size}")
    print(f"Busy timeout: {args.timeout} seconds")
    print(f"-------------------\n")
    
    return display_message(args.message, args.nvme, args.mock, args.font_size, args.timeout)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 