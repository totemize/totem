from devices.eink.eink import EInk
from PIL import Image, ImageDraw, ImageFont
from utils.logger import logger
from typing import Optional

class DisplayManager:
    def __init__(self, driver_name: Optional[str] = None):
        try:
            logger.debug(f"Initializing DisplayManager with driver: {driver_name if driver_name else 'auto-detect'}")
            self.eink_device = EInk(driver_name)
            self.eink_device.initialize()
            logger.info(f"Display dimensions: {self.eink_device.driver.width}x{self.eink_device.driver.height}")
        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            raise

    def clear_screen(self):
        try:
            logger.debug("Clearing screen")
            self.eink_device.clear_display()
        except Exception as e:
            logger.error(f"Error clearing screen: {e}")
            raise

    def display_text(self, text: str, font_size: int = 24):
        try:
            logger.info(f"Displaying text: {text}")
            image = Image.new('1', (self.eink_device.driver.width, self.eink_device.driver.height), 255)
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((10, 10), text, font=font, fill=0)
            self.eink_device.display_image(image)
        except Exception as e:
            logger.error(f"Error displaying text: {e}")
            raise

    def display_image_from_file(self, file_path: str):
        try:
            logger.info(f"Displaying image from file: {file_path}")
            image = Image.open(file_path)
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
