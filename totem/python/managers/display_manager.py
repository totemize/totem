from devices.eink.eink import EInk
from devices.eink.eink_client import EInkClient
from PIL import Image, ImageDraw, ImageFont
from utils.logger import logger
from typing import Optional
import os
import io

class DisplayManager:
    """
    Manager for interacting with the e-ink display
    
    This class can operate in two modes:
    1. Direct hardware access (legacy mode) - directly initializes and controls the e-ink display
    2. Client mode - communicates with the eink_service process that maintains exclusive GPIO access
    
    The mode is determined by the USE_EINK_SERVICE environment variable:
    - If USE_EINK_SERVICE=1, client mode is used
    - Otherwise, direct hardware access is used
    """
    
    def __init__(self, driver_name: Optional[str] = None):
        """
        Initialize the DisplayManager
        
        Args:
            driver_name: Specific driver to use (e.g., 'waveshare_3in7')
        """
        # Determine whether to use the EInk service or direct hardware access
        self.use_service = os.environ.get('USE_EINK_SERVICE', '0') == '1'
        
        try:
            # If in test mode (environment variable), force direct hardware access
            if os.environ.get('EINK_TEST_MODE', '0') == '1':
                self.use_service = False
                logger.info("Test mode enabled, using direct hardware access")
            
            if self.use_service:
                logger.debug("Initializing DisplayManager in client mode")
                self.eink_client = EInkClient()
                self.eink_device = None  # We don't need a direct device in client mode
            else:
                logger.debug(f"Initializing DisplayManager in direct hardware mode with driver: {driver_name if driver_name else 'auto-detect'}")
                self.eink_device = EInk(driver_name)
                self.eink_client = None
                
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
        """Clear the e-ink display"""
        try:
            logger.debug("Clearing screen")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.clear_screen()
                if response.get('status') != 'queued':
                    logger.error(f"Failed to clear screen via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
                # For 3.7 inch display, need to clear with specific parameters
                if hasattr(self.eink_device.driver, 'WIDTH') and self.eink_device.driver.WIDTH == 280:  # 3.7 inch is 280x480
                    logger.debug("Using specific clear method for 3.7 inch display")
                    self.eink_device.driver.clear(0xFF, 0)  # Use the specific clear method for 3.7 inch
                else:
                    self.eink_device.clear_display()
        except Exception as e:
            logger.error(f"Error clearing screen: {e}")
            raise

    def display_text(self, text: str, font_size: int = 24, x: int = 10, y: int = 10, font_name: Optional[str] = None):
        """
        Display text on the e-ink display
        
        Args:
            text: Text to display
            font_size: Font size in pixels
            x: X coordinate for text position
            y: Y coordinate for text position
            font_name: Path to font file (optional)
        """
        try:
            logger.info(f"Displaying text: {text}")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.display_text(text, font_size=font_size, x=x, y=y, font=font_name)
                if response.get('status') != 'queued':
                    logger.error(f"Failed to display text via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
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
                
                # Load font
                try:
                    if font_name:
                        font = ImageFont.truetype(font_name, font_size)
                    else:
                        font = ImageFont.load_default()
                except Exception as e:
                    logger.warning(f"Could not load font, using default: {e}")
                    font = ImageFont.load_default()
                
                draw.text((x, y), text, font=font, fill=0)
                
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
        """
        Display an image from a file on the e-ink display
        
        Args:
            file_path: Path to the image file
        """
        try:
            logger.info(f"Displaying image from file: {file_path}")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.display_image(image_path=file_path)
                if response.get('status') != 'queued':
                    logger.error(f"Failed to display image via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
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

    def display_image(self, image):
        """
        Display a PIL Image object on the e-ink display
        
        Args:
            image: PIL Image object to display
        """
        try:
            logger.info("Displaying PIL Image")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.display_image(image=image)
                if response.get('status') != 'queued':
                    logger.error(f"Failed to display image via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
                # Use the appropriate display method based on display type
                if hasattr(self.eink_device.driver, 'display_4Gray') and '3in7' in type(self.eink_device.driver).__name__:
                    # For 3.7 inch display, use 4Gray mode
                    buffer = self.eink_device.driver.getbuffer_4Gray(image) if hasattr(self.eink_device.driver, 'getbuffer_4Gray') else image
                    self.eink_device.driver.display_4Gray(buffer)
                else:
                    # For other displays, use standard display method
                    self.eink_device.display_image(image)
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            raise

    def display_bytes(self, image_bytes):
        """
        Display image from raw bytes
        
        Args:
            image_bytes: Raw image bytes
        """
        try:
            logger.info("Displaying raw byte data via DisplayManager.")
            
            if self.use_service:
                # Convert bytes to image and use the service
                image = Image.open(io.BytesIO(image_bytes))
                response = self.eink_client.display_image(image=image)
                if response.get('status') != 'queued':
                    logger.error(f"Failed to display image bytes via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
                self.eink_device.display_bytes(image_bytes)
        except Exception as e:
            logger.error(f"Error displaying byte data: {e}")
            raise

    def sleep(self):
        """Put the display to sleep to save power"""
        try:
            logger.info("Putting display to sleep")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.sleep_display()
                if response.get('status') != 'queued':
                    logger.error(f"Failed to sleep display via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
                if hasattr(self.eink_device.driver, 'sleep'):
                    self.eink_device.driver.sleep()
                else:
                    logger.warning("Sleep not supported by this display driver")
        except Exception as e:
            logger.error(f"Error sleeping display: {e}")
            raise

    def wake(self):
        """Wake up the display from sleep mode"""
        try:
            logger.info("Waking up display")
            
            if self.use_service:
                # Use the EInk service
                response = self.eink_client.wake_display()
                if response.get('status') != 'queued':
                    logger.error(f"Failed to wake display via service: {response.get('message', 'Unknown error')}")
                    raise Exception(f"Service error: {response.get('message', 'Unknown error')}")
            else:
                # Direct hardware access (legacy mode)
                # Different displays may have different wake methods
                self.eink_device.initialize()
        except Exception as e:
            logger.error(f"Error waking display: {e}")
            raise
