from devices.eink.eink import EInk
from PIL import Image, ImageDraw, ImageFont
from utils.logger import logger
from typing import Optional

class DisplayManager:
    def __init__(self, driver_name: Optional[str] = None):
        try:
            logger.debug(f"Initializing DisplayManager with driver: {driver_name if driver_name else 'auto-detect'}")
            self.eink_device = EInk(driver_name)
            
            # Initialize with parameters if it's the 3.7 inch display (like in manufacturer example)
            if driver_name and ('3in7' in driver_name):
                logger.debug("Initializing 3.7 inch display with parameter 0")
                self.eink_device.driver.init(0)  # 3.7 inch display requires a parameter
            else:
                self.eink_device.initialize()
                
            logger.info(f"Display dimensions: {self.eink_device.driver.width}x{self.eink_device.driver.height}")
        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            raise

    def clear_screen(self):
        try:
            logger.debug("Clearing screen")
            # For 3.7 inch display, need to clear with specific parameters
            if hasattr(self.eink_device.driver, 'WIDTH') and self.eink_device.driver.WIDTH == 280:  # 3.7 inch is 280x480
                logger.debug("Using specific clear method for 3.7 inch display")
                self.eink_device.driver.clear(0xFF, 0)  # Use the specific clear method for 3.7 inch
            else:
                self.eink_device.clear_display()
        except Exception as e:
            logger.error(f"Error clearing screen: {e}")
            raise

    def display_text(self, text: str, font_size: int = 24):
        try:
            logger.info(f"Displaying text: {text}")
            # Create an image with the correct dimensions and mode for the display
            if hasattr(self.eink_device.driver, 'WIDTH'):
                width = self.eink_device.driver.WIDTH
                height = self.eink_device.driver.HEIGHT
            else:
                width = self.eink_device.driver.width
                height = self.eink_device.driver.height
                
            # 3.7 inch display supports grayscale, others are black and white
            if hasattr(self.eink_device.driver, 'WIDTH') and self.eink_device.driver.WIDTH == 280:
                image = Image.new('L', (width, height), 255)  # 'L' mode for grayscale
            else:
                image = Image.new('1', (width, height), 255)  # '1' mode for black and white
                
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((10, 10), text, font=font, fill=0)
            
            # Use the appropriate display method based on display type
            if hasattr(self.eink_device.driver, 'display_4Gray') and '3in7' in type(self.eink_device.driver).__name__:
                # For 3.7 inch display, use 4Gray mode
                buffer = self.eink_device.driver.getbuffer_4Gray(image) if hasattr(self.eink_device.driver, 'getbuffer_4Gray') else image
                self.eink_device.driver.display_4Gray(buffer)
            else:
                # For other displays, use standard display method
                self.eink_device.display_image(image)
        except Exception as e:
            logger.error(f"Error displaying text: {e}")
            raise

    def display_image_from_file(self, file_path: str):
        try:
            logger.info(f"Displaying image from file: {file_path}")
            image = Image.open(file_path)
            
            # Use the appropriate display method based on display type
            if hasattr(self.eink_device.driver, 'display_4Gray') and '3in7' in type(self.eink_device.driver).__name__:
                # For 3.7 inch display, use 4Gray mode
                buffer = self.eink_device.driver.getbuffer_4Gray(image) if hasattr(self.eink_device.driver, 'getbuffer_4Gray') else image
                self.eink_device.driver.display_4Gray(buffer)
            else:
                # For other displays, use standard display method
                self.eink_device.display_image(image)
        except Exception as e:
            logger.error(f"Error displaying image from file: {e}")
            raise

    def display_bytes(self, image_bytes):
        try:
            logger.info("Displaying raw byte data via DisplayManager.")
            self.eink_device.display_bytes(image_bytes)
        except Exception as e:
            logger.error(f"Error displaying byte data: {e}")
            raise
