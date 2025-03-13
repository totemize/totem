#!/usr/bin/env python3
"""
E-Ink Display Example

This example demonstrates how to:
1. Initialize the e-ink display
2. Display text in different sizes and positions
3. Display images
4. Show a combination of text and images
5. Use both 1-Gray and 4-Gray modes

Usage:
    python3 eink_display_example.py [--mock] [--nvme-compatible]

Options:
    --mock              Run in mock mode without hardware
    --nvme-compatible   Use NVME-compatible pin configuration
"""

import os
import sys
import time
import argparse
from PIL import Image, ImageDraw, ImageFont

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the e-ink driver
from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7


def display_text_example(epd):
    """Example of displaying text in different styles"""
    print("Starting text display example...")
    
    # Initialize the display in 4-Gray mode
    epd.init(mode=0)
    epd.Clear(0xFF, mode=0)  # Clear to white
    
    # Create a new blank image for drawing (white background)
    width, height = epd.width, epd.height
    image = Image.new('L', (width, height), 255)  # 255: white
    draw = ImageDraw.Draw(image)
    
    # Try to load fonts in different sizes
    fonts = {}
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
        '/usr/share/fonts/TTF/DejaVuSans.ttf',              # Other Linux
        '/System/Library/Fonts/Helvetica.ttc',               # macOS
        'C:\\Windows\\Fonts\\Arial.ttf',                     # Windows
    ]
    
    # Find a working font
    font_path = None
    for path in font_paths:
        if os.path.exists(path):
            font_path = path
            break
    
    if font_path:
        # Load different font sizes
        try:
            fonts['small'] = ImageFont.truetype(font_path, 16)
            fonts['medium'] = ImageFont.truetype(font_path, 24)
            fonts['large'] = ImageFont.truetype(font_path, 36)
            fonts['xl'] = ImageFont.truetype(font_path, 48)
        except Exception as e:
            print(f"Error loading fonts: {e}")
            fonts['small'] = ImageFont.load_default()
            fonts['medium'] = ImageFont.load_default()
            fonts['large'] = ImageFont.load_default()
            fonts['xl'] = ImageFont.load_default()
    else:
        # Use default font if no TrueType fonts available
        print("No TrueType fonts found, using default font")
        fonts['small'] = ImageFont.load_default()
        fonts['medium'] = ImageFont.load_default()
        fonts['large'] = ImageFont.load_default()
        fonts['xl'] = ImageFont.load_default()
    
    # Draw text at different positions with different font sizes
    draw.text((10, 10), "Hello, E-Ink Display!", font=fonts['large'], fill=0)  # 0: black
    draw.text((10, 60), "This is medium text", font=fonts['medium'], fill=85)  # 85: dark gray (approx GRAY2)
    draw.text((10, 100), "This is small text", font=fonts['small'], fill=170)  # 170: light gray (approx GRAY3)
    draw.text((10, 130), "BIG TEXT", font=fonts['xl'], fill=0)  # 0: black
    
    # Draw a line underneath the text
    draw.line((10, 200, width-10, 200), fill=0, width=2)
    
    # Add more info text
    draw.text((10, 220), "Width: {} pixels".format(width), font=fonts['small'], fill=0)
    draw.text((10, 240), "Height: {} pixels".format(height), font=fonts['small'], fill=0)
    draw.text((10, 260), "Time: {}".format(time.strftime("%H:%M:%S")), font=fonts['medium'], fill=0)
    draw.text((10, 290), "Date: {}".format(time.strftime("%Y-%m-%d")), font=fonts['medium'], fill=0)
    
    # Display the image
    epd.display(image)
    print("Text display example completed")
    
    # Wait to show the image
    time.sleep(3)


def display_shapes_example(epd):
    """Example of drawing various shapes"""
    print("Starting shapes example...")
    
    # Initialize the display if needed
    if not epd.initialized:
        epd.init(mode=0)
    
    # Clear to white
    epd.Clear(0xFF, mode=0)
    
    # Create a new blank image for drawing
    width, height = epd.width, epd.height
    image = Image.new('L', (width, height), 255)  # 255: white
    draw = ImageDraw.Draw(image)
    
    # Draw a rectangle
    draw.rectangle((20, 20, 120, 120), outline=0, fill=85)  # dark gray fill
    
    # Draw a circle
    draw.ellipse((150, 20, 250, 120), outline=0, fill=170)  # light gray fill
    
    # Draw a triangle (polygon)
    draw.polygon([(50, 150), (150, 250), (50, 350)], outline=0, fill=0)  # black fill
    
    # Draw lines with different thickness
    for i in range(1, 6):
        draw.line((width-100, 20+i*30, width-20, 20+i*30), fill=0, width=i)
    
    # Display the image
    epd.display(image)
    print("Shapes example completed")
    
    # Wait to show the image
    time.sleep(3)


def display_image_example(epd, image_path=None):
    """Example of displaying an image from file or a generated image"""
    print("Starting image display example...")
    
    # Initialize the display if needed
    if not epd.initialized:
        epd.init(mode=0)
    
    # Clear to white
    epd.Clear(0xFF, mode=0)
    
    width, height = epd.width, epd.height
    
    # Try to open the provided image if it exists
    if image_path and os.path.exists(image_path):
        print(f"Loading image from: {image_path}")
        image = Image.open(image_path)
        # Resize the image to fit the display
        image = image.resize((width, height), Image.LANCZOS)
        # Convert to grayscale if it's not already
        if image.mode != 'L':
            image = image.convert('L')
    else:
        print("No image provided or file not found. Generating a test pattern...")
        # Generate a test pattern image
        image = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(image)
        
        # Create a gradient pattern
        for x in range(0, width, 4):
            for y in range(0, height, 4):
                # Create a gradient pattern based on position
                gray_value = (x * y) % 255
                draw.rectangle((x, y, x+3, y+3), fill=gray_value)
        
        # Add some text to the image
        font = ImageFont.load_default()
        draw.text((width//2-50, height//2), "Test Image", font=font, fill=0)
    
    # Display the image
    epd.display(image)
    print("Image display example completed")
    
    # Wait to show the image
    time.sleep(3)


def combined_example(epd):
    """Example that combines text and graphics"""
    print("Starting combined example...")
    
    # Initialize the display if needed
    if not epd.initialized:
        epd.init(mode=0)
    
    # Clear to white
    epd.Clear(0xFF, mode=0)
    
    width, height = epd.width, epd.height
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    
    # Try to find a suitable font
    font_path = None
    for path in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        'C:\\Windows\\Fonts\\Arial.ttf'
    ]:
        if os.path.exists(path):
            font_path = path
            break
    
    # Load fonts with different sizes
    try:
        if font_path:
            title_font = ImageFont.truetype(font_path, 36)
            text_font = ImageFont.truetype(font_path, 20)
        else:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # Draw a border
    draw.rectangle((0, 0, width-1, height-1), outline=0)
    
    # Draw a title
    title = "E-Ink Display Demo"
    draw.text((width//2-100, 10), title, font=title_font, fill=0)
    
    # Draw a horizontal line
    draw.line((20, 60, width-20, 60), fill=0, width=2)
    
    # Draw some shapes
    # Circle on the left
    draw.ellipse((30, 80, 130, 180), outline=0, fill=170)
    # Rectangle on the right
    draw.rectangle((width-130, 80, width-30, 180), outline=0, fill=85)
    
    # Add some text in the middle
    text = "This is a combined example\nshowing text and graphics\ntogether on the display."
    draw.multiline_text((width//2-100, 100), text, font=text_font, fill=0, align="center")
    
    # Draw a horizontal line
    draw.line((20, 200, width-20, 200), fill=0, width=2)
    
    # Add a table-like structure
    table_y = 220
    column_width = width // 3
    
    # Table headers
    draw.rectangle((20, table_y, width-20, table_y+30), outline=0, fill=85)
    draw.text((30, table_y+5), "Column 1", font=text_font, fill=0)
    draw.text((30+column_width, table_y+5), "Column 2", font=text_font, fill=0)
    draw.text((30+column_width*2, table_y+5), "Column 3", font=text_font, fill=0)
    
    # Table rows
    for i in range(3):
        row_y = table_y + 30 + (i * 30)
        # Draw row outline
        draw.rectangle((20, row_y, width-20, row_y+30), outline=0)
        # Draw cell content
        draw.text((30, row_y+5), f"Row {i+1}-1", font=text_font, fill=0)
        draw.text((30+column_width, row_y+5), f"Row {i+1}-2", font=text_font, fill=0)
        draw.text((30+column_width*2, row_y+5), f"Row {i+1}-3", font=text_font, fill=0)
    
    # Add current time at the bottom
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((width//2-100, height-40), current_time, font=text_font, fill=0)
    
    # Display the image
    epd.display(image)
    print("Combined example completed")
    
    # Wait to show the image
    time.sleep(3)


def one_gray_mode_example(epd):
    """Example using 1-Gray mode (black and white only)"""
    print("Starting 1-Gray mode example...")
    
    # Initialize the display in 1-Gray mode
    epd.init(mode=1)
    epd.Clear(0xFF, mode=1)  # Clear to white
    
    width, height = epd.width, epd.height
    image = Image.new('1', (width, height), 255)  # '1' mode is 1-bit (black and white)
    draw = ImageDraw.Draw(image)
    
    # Draw a black and white checkerboard pattern
    square_size = 40
    for x in range(0, width, square_size):
        for y in range(0, height, square_size):
            # Alternate black and white squares
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                draw.rectangle((x, y, x+square_size, y+square_size), fill=0)  # Black
    
    # Try to load a font
    font = None
    for path in [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        'C:\\Windows\\Fonts\\Arial.ttf'
    ]:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 36)
                break
            except Exception:
                pass
    
    if font is None:
        font = ImageFont.load_default()
    
    # Add text overlay
    draw.text((width//2-120, height//2-20), "1-Gray Mode", font=font, fill=255)  # White text
    
    # Get buffer for 1-Gray mode
    buffer = epd.getbuffer(image)
    
    # Display using 1-Gray mode
    epd.display_1Gray(buffer)
    print("1-Gray mode example completed")
    
    # Wait to show the image
    time.sleep(3)


def main():
    """Main function to run the e-ink display examples"""
    parser = argparse.ArgumentParser(description='E-Ink Display Example')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without hardware')
    parser.add_argument('--nvme-compatible', action='store_true', help='Use NVME-compatible pin configuration')
    parser.add_argument('--image', type=str, help='Path to an image file to display')
    args = parser.parse_args()
    
    # Set environment variables based on arguments
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
    if args.nvme_compatible:
        os.environ['NVME_COMPATIBLE'] = '1'
    
    try:
        # Initialize the display
        print("Initializing E-Ink display...")
        epd = WaveshareEPD3in7()
        
        print("\nDisplay dimensions:")
        print(f"Width: {epd.width} pixels")
        print(f"Height: {epd.height} pixels")
        print(f"Running in mock mode: {epd.mock_mode}")
        print(f"NVME compatible mode: {epd.nvme_compatible}")
        print()
        
        # Run the examples
        display_text_example(epd)
        display_shapes_example(epd)
        display_image_example(epd, args.image)
        combined_example(epd)
        one_gray_mode_example(epd)
        
        print("All examples completed")
        
        # Clear and sleep
        epd.init(0)
        epd.Clear(0xFF, 0)
        epd.sleep()
        
    except KeyboardInterrupt:
        print("Exiting due to keyboard interrupt")
        if 'epd' in locals():
            epd.init(0)
            epd.Clear(0xFF, 0)
            epd.sleep()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Exiting e-ink display example")


if __name__ == '__main__':
    main() 