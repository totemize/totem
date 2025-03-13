#!/usr/bin/env python3
"""
Direct Test of Waveshare E-Ink Display

This script directly uses our Driver class which has better error handling.
It performs a similar test to the manufacturer's example but uses our wrapper.

Run with sudo for proper GPIO access:
    sudo python3 run_direct_test.py
"""

import os
import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("eink_test")

def main():
    # Check if running as root
    if os.geteuid() != 0:
        logger.error("This script must be run as root (sudo). Exiting.")
        sys.exit(1)
    
    # Add our local package to the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # Print current directory and sys.path for debugging
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Script directory: {script_dir}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"Initial sys.path: {sys.path}")
    
    # Add all possible paths to sys.path
    sys.path.insert(0, project_root)  # Add project root
    sys.path.insert(0, os.path.dirname(project_root))  # Add parent of project root
    
    logger.info(f"Updated sys.path: {sys.path}")
    
    # Try to import the driver
    driver_imported = False
    
    # Try all possible import paths
    import_attempts = [
        "from devices.eink.drivers.waveshare_3in7 import Driver",
        "from python.devices.eink.drivers.waveshare_3in7 import Driver",
        "from totem.devices.eink.drivers.waveshare_3in7 import Driver",
        "from totem.python.devices.eink.drivers.waveshare_3in7 import Driver"
    ]
    
    Driver = None
    for attempt in import_attempts:
        try:
            logger.info(f"Trying import: {attempt}")
            exec(attempt)
            logger.info("Import successful!")
            driver_imported = True
            break
        except ImportError as e:
            logger.warning(f"Import failed: {e}")
    
    if not driver_imported:
        # Last resort: try to find the file directly and import it
        logger.info("Trying direct file import...")
        
        possible_driver_files = [
            os.path.join(project_root, "devices", "eink", "drivers", "waveshare_3in7.py"),
            os.path.join(project_root, "python", "devices", "eink", "drivers", "waveshare_3in7.py"),
            os.path.join(os.path.dirname(project_root), "devices", "eink", "drivers", "waveshare_3in7.py"),
            os.path.join(os.path.dirname(project_root), "python", "devices", "eink", "drivers", "waveshare_3in7.py"),
        ]
        
        driver_file = None
        for path in possible_driver_files:
            if os.path.exists(path):
                driver_file = path
                logger.info(f"Found driver file at: {path}")
                
                # Add the directory to sys.path
                driver_dir = os.path.dirname(path)
                sys.path.insert(0, os.path.dirname(driver_dir))  # Add eink directory
                sys.path.insert(0, os.path.dirname(os.path.dirname(driver_dir)))  # Add devices directory
                
                try:
                    if "python/devices" in path:
                        from python.devices.eink.drivers.waveshare_3in7 import Driver
                    elif "devices/eink" in path:
                        from devices.eink.drivers.waveshare_3in7 import Driver
                    else:
                        # Try a relative import based on the file path
                        module_path = os.path.relpath(path, project_root).replace("/", ".").replace(".py", "")
                        exec(f"from {module_path} import Driver")
                    
                    logger.info("Successfully imported Driver class")
                    driver_imported = True
                    break
                except ImportError as e:
                    logger.warning(f"Import failed even with direct path: {e}")
        
    if not driver_imported:
        logger.error("Could not import Driver class. Please check your project structure.")
        sys.exit(1)
    
    # Import other required packages
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Failed to import PIL. Please install it with: sudo apt-get install python3-pil")
        sys.exit(1)
    
    # Find a suitable font
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    ]
    
    font36 = None
    font24 = None
    font18 = None
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                font36 = ImageFont.truetype(path, 36)
                font24 = ImageFont.truetype(path, 24)
                font18 = ImageFont.truetype(path, 18)
                logger.info(f"Using font: {path}")
                break
            except Exception:
                pass
    
    if font36 is None:
        logger.warning("No TrueType fonts found, using default")
        font36 = ImageFont.load_default()
        font24 = ImageFont.load_default()
        font18 = ImageFont.load_default()
    
    # Run the test
    try:
        logger.info("E-Ink Display Test")
        
        # Initialize the driver
        driver = Driver()
        logger.info("Initializing display...")
        driver.init()
        driver.clear()
        
        # Test display_text method
        logger.info("Testing display_text method...")
        driver.display_text("Hello from Totem!", 10, 10, 36)
        time.sleep(3)
        
        # Draw on the display
        logger.info("Drawing on the display...")
        Himage = Image.new('L', (driver.width, driver.height), 0xFF)  # 0xFF: clear the frame
        draw = ImageDraw.Draw(Himage)
        
        # Draw text
        draw.text((10, 0), 'Hello from Totem!', font=font24, fill=0)
        draw.text((10, 30), '3.7inch E-Ink Test', font=font24, fill=0)
        
        # Draw shapes with different gray levels
        draw.rectangle((10, 70, 150, 110), 'black', 'black')
        draw.text((10, 70), 'Waveshare', font=font36, fill=driver.GRAY1)
        draw.text((10, 120), 'E-Paper', font=font36, fill=driver.GRAY2)
        draw.text((10, 170), 'Demo', font=font36, fill=driver.GRAY3)
        draw.text((10, 220), 'Test', font=font36, fill=driver.GRAY4)
        
        # Draw lines and shapes
        draw.line((180, 50, 230, 100), fill=0)
        draw.line((230, 50, 180, 100), fill=0)
        draw.rectangle((180, 50, 230, 100), outline=0)
        draw.arc((240, 50, 290, 100), 0, 360, fill=0)
        draw.rectangle((300, 50, 350, 100), fill=0)
        
        # Display the image
        logger.info("Displaying image...")
        driver.display_image(Himage)
        
        # Wait for 5 seconds
        logger.info("Waiting for 5 seconds...")
        time.sleep(5)
        
        # Clear the display
        logger.info("Clearing display...")
        driver.clear()
        
        # Display text at different positions
        logger.info("Displaying text at different positions...")
        driver.display_text("Top Left", 10, 10, 24)
        driver.display_text("Top Right", 300, 10, 24)
        driver.display_text("Bottom Left", 10, 200, 24)
        driver.display_text("Bottom Right", 300, 200, 24)
        driver.display_text("Center", 200, 120, 36)
        
        # Wait for 5 seconds
        time.sleep(5)
        
        # Clear the display
        logger.info("Clearing display...")
        driver.clear()
        
        # Put the display to sleep
        logger.info("Putting display to sleep...")
        driver.sleep()
        
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to clean up
        try:
            driver.close()
        except:
            pass
        
        sys.exit(1)

if __name__ == "__main__":
    main() 