#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Test script for the e-ink display using our driver that wraps the manufacturer's code.
This script follows the manufacturer's test approach exactly.
"""

import sys
import os
import logging
import time
import argparse
from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Import our driver
from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7

logging.basicConfig(level=logging.DEBUG)

def main():
    parser = argparse.ArgumentParser(description='Test the e-ink display using our driver with manufacturer approach')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without physical hardware')
    parser.add_argument('--nvme', action='store_true', help='Use NVME-compatible pin configuration')
    args = parser.parse_args()
    
    # Set environment variables based on arguments
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
    if args.nvme:
        os.environ['NVME_COMPATIBLE'] = '1'
    
    try:
        logging.info("E-ink Display Test")
        
        # Initialize the display
        epd = WaveshareEPD3in7()
        
        logging.info("Initializing and clearing display")
        epd.init(0)  # 0 = 4Gray mode
        epd.Clear(0xFF, 0)
        
        # Try to find a font
        try:
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            if os.path.exists(font_path):
                font36 = ImageFont.truetype(font_path, 36)
                font24 = ImageFont.truetype(font_path, 24)
                font18 = ImageFont.truetype(font_path, 18)
            else:
                logging.info("Default font not found, using load_default()")
                font36 = ImageFont.load_default()
                font24 = ImageFont.load_default()
                font18 = ImageFont.load_default()
        except Exception as e:
            logging.error(f"Font error: {e}")
            font36 = ImageFont.load_default()
            font24 = ImageFont.load_default()
            font18 = ImageFont.load_default()
        
        # 1. Drawing on the Horizontal image
        logging.info("1. Drawing on the Horizontal image...")
        Himage = Image.new('L', (epd.height, epd.width), 0xFF)  # 0xFF: clear the frame
        draw = ImageDraw.Draw(Himage)
        draw.text((10, 0), 'hello world', font=font24, fill=0)
        draw.text((10, 20), '3.7inch e-Paper', font=font24, fill=0)
        draw.rectangle((10, 110, 154, 146), 'black', 'black')
        draw.text((10, 110), 'Totem Test', font=font36, fill=epd.GRAY1)
        draw.text((10, 150), 'Totem Test', font=font36, fill=epd.GRAY2)
        draw.text((10, 190), 'Totem Test', font=font36, fill=epd.GRAY3)
        draw.text((10, 230), 'Totem Test', font=font36, fill=epd.GRAY4)
        draw.line((20, 50, 70, 100), fill=0)
        draw.line((70, 50, 20, 100), fill=0)
        draw.rectangle((20, 50, 70, 100), outline=0)
        draw.line((165, 50, 165, 100), fill=0)
        draw.line((140, 75, 190, 75), fill=0)
        draw.arc((140, 50, 190, 100), 0, 360, fill=0)
        draw.rectangle((80, 50, 130, 100), fill=0)
        draw.chord((200, 50, 250, 100), 0, 360, fill=0)
        
        # Display the image exactly as in the manufacturer's example
        logging.info("Displaying image using 4Gray mode")
        epd.display_4Gray(epd.getbuffer_4Gray(Himage))
        time.sleep(5)
            
        # 4. Drawing on the Vertical image
        logging.info("2. Drawing on the Vertical image...")
        Limage = Image.new('L', (epd.width, epd.height), 0xFF)  # 0xFF: clear the frame
        draw = ImageDraw.Draw(Limage)
        draw.text((2, 0), 'hello world', font=font18, fill=0)
        draw.text((2, 20), '3.7inch epd', font=font18, fill=0)
        draw.rectangle((130, 20, 274, 56), 'black', 'black')
        draw.text((130, 20), 'Totem Test', font=font36, fill=epd.GRAY1)
        draw.text((130, 60), 'Totem Test', font=font36, fill=epd.GRAY2)
        draw.text((130, 100), 'Totem Test', font=font36, fill=epd.GRAY3)
        draw.text((130, 140), 'Totem Test', font=font36, fill=epd.GRAY4)
        draw.line((10, 90, 60, 140), fill=0)
        draw.line((60, 90, 10, 140), fill=0)
        draw.rectangle((10, 90, 60, 140), outline=0)
        draw.line((95, 90, 95, 140), fill=0)
        draw.line((70, 115, 120, 115), fill=0)
        draw.arc((70, 90, 120, 140), 0, 360, fill=0)
        draw.rectangle((10, 150, 60, 200), fill=0)
        draw.chord((70, 150, 120, 200), 0, 360, fill=0)
        
        # Display the image exactly as in the manufacturer's example
        logging.info("Displaying image using 4Gray mode")
        epd.display_4Gray(epd.getbuffer_4Gray(Limage))
        time.sleep(5)
            
        # partial update, just 1 Gray mode
        logging.info("3. Show time with partial update (1 Gray mode)")
        epd.init(1)         # 1 Gray mode
        epd.Clear(0xFF, 1)  # Clear for 1 Gray mode
        
        time_image = Image.new('1', (epd.height, epd.width), 255)
        time_draw = ImageDraw.Draw(time_image)
        
        # Display time for a few iterations
        for i in range(5):  # Reduced to 5 iterations for testing
            time_draw.rectangle((10, 10, 120, 50), fill=255)
            time_draw.text((10, 10), time.strftime('%H:%M:%S'), font=font24, fill=0)
            epd.display_1Gray(epd.getbuffer(time_image))
            time.sleep(1)
            
        # Clear display at the end
        logging.info("Clearing display...")
        epd.init(0)
        epd.Clear(0xFF, 0)
        
        # Put display to sleep
        logging.info("Going to sleep...")
        epd.sleep()
        
        logging.info("Test completed successfully!")
        return 0
        
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 