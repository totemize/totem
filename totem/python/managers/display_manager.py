from devices.eink.eink import EInk
from PIL import Image, ImageDraw, ImageFont
from utils.logger import logger

class DisplayManager:
    def __init__(self, driver_name: Optional[str] = None):
        self.eink_device = EInk(driver_name)
        self.eink_device.initialize()

    def clear_screen(self):
        self.eink_device.clear_display()

    def display_text(self, text: str, font_size: int = 24):
        logger.info(f"Displaying text: {text}")
        image = Image.new('1', (self.eink_device.driver.width, self.eink_device.driver.height), 255)
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.text((10, 10), text, font=font, fill=0)
        self.eink_device.display_image(image)

    def display_image_from_file(self, file_path: str):
        logger.info(f"Displaying image from file: {file_path}")
        image = Image.open(file_path) #test
        self.eink_device.display_image(image)

    def display_bytes(self, image_bytes):
        logger.info("Displaying raw byte data via DisplayManager.")
        self.eink_device.display_bytes(image_bytes)
