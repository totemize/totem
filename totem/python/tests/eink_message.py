#!/usr/bin/env python3
"""
EInk Message Display Script

A simple script to display messages on the EInk display.
Works in both NVME-compatible mode and regular mode.

Usage:
  python3 eink_message.py "Your message here"
  python3 eink_message.py --nvme "Message with NVME compatibility"
  python3 eink_message.py --mock "Test in mock mode"
  python3 eink_message.py --help
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Add the parent directory to the path
script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent.parent
sys.path.insert(0, str(project_dir))

def display_message(message, nvme_compatible=False, mock_mode=False, font_size=36):
    """Display a message on the EInk display"""
    # Set environment variables
    if nvme_compatible:
        os.environ['NVME_COMPATIBLE'] = '1'
    if mock_mode:
        os.environ['EINK_MOCK_MODE'] = '1'
    
    # Import the EInk driver
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7, RST_PIN, DC_PIN, CS_PIN, BUSY_PIN

    try:
        # Initialize the display
        print("Initializing display...")
        epd = WaveshareEPD3in7()
        
        # Print configuration
        print(f"EInk Display Configuration:")
        print(f"  Mock mode: {epd.mock_mode}")
        print(f"  NVME compatible: {epd.nvme_compatible}")
        print(f"  Software SPI: {epd.using_sw_spi}")
        print(f"  RST_PIN: {RST_PIN}")
        print(f"  DC_PIN: {DC_PIN}")
        print(f"  CS_PIN: {CS_PIN}")
        print(f"  BUSY_PIN: {BUSY_PIN}")
        if epd.using_sw_spi:
            from python.devices.eink.waveshare_3in7 import MOSI_PIN, SCK_PIN
            print(f"  MOSI_PIN: {MOSI_PIN}")
            print(f"  SCK_PIN: {SCK_PIN}")
        
        # Initialize the display
        epd.init()
        print("Display initialized")
        
        # Clear the display
        print("Clearing display...")
        epd.Clear()
        print("Display cleared")
        
        # Display the message (handle multiline messages)
        print("Displaying message:")
        print(message)
        lines = message.split('\n')
        y_position = 10
        for line in lines:
            print(f"Displaying line at y={y_position}: {line}")
            epd.display_text(line, 10, y_position, font_size)
            y_position += int(font_size * 1.5)  # Space lines based on font size
        
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
    
    args = parser.parse_args()
    
    # Print configuration
    print(f"EInk Message Display")
    print(f"-------------------")
    print(f"Message: {args.message}")
    print(f"NVME compatibility: {'Enabled' if args.nvme else 'Disabled'}")
    print(f"Mock mode: {'Enabled' if args.mock else 'Disabled'}")
    print(f"Font size: {args.font_size}")
    print(f"-------------------\n")
    
    return display_message(args.message, args.nvme, args.mock, args.font_size)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 