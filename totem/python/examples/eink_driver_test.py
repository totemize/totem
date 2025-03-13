#!/usr/bin/env python3
"""
E-Ink Driver Direct Test

This script tests the e-ink driver directly by sending commands that will
visually confirm functionality. It creates a checkerboard pattern that will
be clearly visible on the display.

Usage:
    sudo python eink_driver_test.py [--mock]

Options:
    --mock    Run in mock mode without hardware
"""

import os
import sys
import time
import argparse
from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the e-ink driver directly
from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7

def draw_checkerboard(epd, square_size=40):
    """Draw a checkerboard pattern that will be clearly visible"""
    print("Drawing checkerboard pattern...")
    
    # Create a new image
    width, height = epd.width, epd.height
    image = Image.new('L', (width, height), 255)  # 255: white
    draw = ImageDraw.Draw(image)
    
    # Draw checkerboard pattern
    for x in range(0, width, square_size):
        for y in range(0, height, square_size):
            # Alternate black and white squares
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                draw.rectangle((x, y, x+square_size, y+square_size), fill=0)  # 0: black
    
    # Add text to confirm this is from the test script
    try:
        font = ImageFont.load_default()
        current_time = time.strftime("%H:%M:%S")
        draw.text((width//2-70, height//2-10), f"DRIVER TEST\n{current_time}", font=font, fill=127)  # Gray text
    except Exception as e:
        print(f"Error adding text: {e}")
    
    # Display the image
    print("Sending to display...")
    buffer = epd.getbuffer_4Gray(image)
    epd.display_4Gray(buffer)
    
    print("Checkerboard pattern displayed")
    return True

def main():
    """Main function to test the e-ink driver directly"""
    parser = argparse.ArgumentParser(description='E-Ink Driver Test')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without hardware')
    args = parser.parse_args()
    
    # Set environment variables
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
    
    try:
        print("Initializing e-ink driver...")
        
        # Initialize the driver directly
        epd = WaveshareEPD3in7()
        
        # Display driver info
        print(f"Driver details:")
        print(f"  Type: {type(epd).__name__}")
        print(f"  Mock mode: {epd.mock_mode}")
        print(f"  Width: {epd.width} pixels")
        print(f"  Height: {epd.height} pixels")
        
        # Initialize the display
        print("Initializing display...")
        epd.init(mode=0)  # 4Gray mode
        
        # Clear the display
        print("Clearing display...")
        epd.Clear(0xFF, mode=0)
        
        # Draw and display checkerboard pattern
        draw_checkerboard(epd)
        
        # Sleep before exiting
        print("Putting display to sleep...")
        epd.sleep()
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Check if running as root (needed for GPIO access)
    if os.geteuid() != 0 and not ('EINK_MOCK_MODE' in os.environ and os.environ['EINK_MOCK_MODE'] == '1'):
        print("This script needs to be run as root to access GPIO pins.")
        print("Please run with: sudo python eink_driver_test.py")
        sys.exit(1)
    
    main() 