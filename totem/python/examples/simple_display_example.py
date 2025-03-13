#!/usr/bin/env python3
"""
Simple E-Ink Display Example

This example shows the easiest way to interact with the e-ink display
using the high-level DisplayManager abstraction.

Usage:
    python simple_display_example.py [text] [--image=PATH_TO_IMAGE]
"""

import os
import sys
import argparse
from PIL import Image

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the DisplayManager
from managers.display_manager import DisplayManager

def main():
    """Main function to demonstrate simple e-ink display usage"""
    parser = argparse.ArgumentParser(description='Simple E-Ink Display Example')
    parser.add_argument('text', nargs='?', default="totem", help='Text to display')
    parser.add_argument('--image', type=str, help='Path to an image file to display')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode')
    parser.add_argument('--service', action='store_true', help='Use the eink service instead of direct hardware access')
    args = parser.parse_args()
    
    # Set up environment variables based on arguments
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
    if args.service:
        os.environ['USE_EINK_SERVICE'] = '1'
    
    try:
        # Create a DisplayManager instance
        # It will automatically use the right driver based on hardware detection
        display = DisplayManager()
        
        # Clear the screen first
        display.clear_screen()
        
        # If an image was provided, display it
        if args.image and os.path.exists(args.image):
            print(f"Displaying image: {args.image}")
            display.display_image_from_file(args.image)
        else:
            # Otherwise, display the text
            print(f"Displaying text: {args.text}")
            # Use a larger font for better readability
            display.display_text(args.text, font_size=36, x=10, y=10)
        
        # Let the display refresh and then put it to sleep
        # This helps conserve power
        display.sleep()
        
        print("Display operation completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 