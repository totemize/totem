from devices.eink.eink import EInkDeviceInterface
from utils.logger import logger
from PIL import Image
import time
import numpy as np

# Mock implementations to replace hardware-dependent libraries
class MockSpiDev:
    def __init__(self, bus=0, device=0):
        self.bus = bus
        self.device = device
        self.max_speed_hz = 0
        logger.debug(f"Initialized mock SPI device on bus {bus}, device {device}")
    
    def writebytes(self, data):
        logger.debug(f"SPI write: {data[:10]}{'...' if len(data) > 10 else ''}")
        return
    
    def close(self):
        logger.debug("SPI connection closed")
        return

class MockGPIO:
    BCM = 1
    OUT = 1
    IN = 0
    HIGH = 1
    LOW = 0
    
    @staticmethod
    def setmode(mode):
        logger.debug(f"GPIO mode set to {mode}")
        return
    
    @staticmethod
    def setup(pin, mode):
        logger.debug(f"GPIO pin {pin} set to mode {mode}")
        return
    
    @staticmethod
    def output(pin, value):
        logger.debug(f"GPIO pin {pin} set to {value}")
        return
    
    @staticmethod
    def input(pin):
        logger.debug(f"Reading GPIO pin {pin}")
        return 1  # Always return idle for testing
    
    @staticmethod
    def cleanup():
        logger.debug("GPIO cleanup complete")
        return

# Use mock implementations instead of hardware libraries
try:
    import spidev
    import RPi.GPIO as GPIO
    logger.info("Using hardware SPI and GPIO")
except ImportError:
    logger.warning("Hardware SPI and GPIO not available, using mock implementations")
    spidev = MockSpiDev
    GPIO = MockGPIO

class Driver(EInkDeviceInterface):
    # Display dimensions
    WIDTH = 280
    HEIGHT = 480
    width = 280
    height = 480
    
    # Grayscale levels
    GRAY1 = 0xFF  # white
    GRAY2 = 0xC0  # light gray
    GRAY3 = 0x80  # dark gray
    GRAY4 = 0x00  # black
    
    def __init__(self):
        self.initialized = False
        logger.info("Initializing Waveshare 3.7inch e-Paper driver")

        # Import hardware libraries if available
        try:
            import spidev
            import RPi.GPIO as GPIO
            self.SPI = spidev.SpiDev()
            self.GPIO = GPIO
            self.hardware_available = True
            logger.info("Hardware libraries successfully imported")
        except ImportError:
            logger.warning("Hardware libraries not available, using mock mode")
            self.SPI = MockSpiDev()
            self.GPIO = MockGPIO
            self.hardware_available = False
        
        # Define GPIO pins
        self.RST_PIN = 17
        self.DC_PIN = 25
        self.BUSY_PIN = 24
        self.CS_PIN = 8

    def init(self, mode=0):
        logger.info(f"Initializing display with mode {mode}")
        if self.hardware_available:
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
            self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
            self.GPIO.setup(self.BUSY_PIN, self.GPIO.IN)
            self.GPIO.setup(self.CS_PIN, self.GPIO.OUT)
            
            # Initialize SPI
            self.SPI.open(0, 0)
            self.SPI.max_speed_hz = 4000000
            self.SPI.mode = 0b00
        
        # Reset and initialize display
        self.reset()
        
        # Send init commands based on mode
        self.send_command(0x12)  # SWRESET
        self.wait_until_idle()
        
        # Add initialization commands similar to manufacturer's code
        self.send_command(0x46)  # Auto Write Red RAM
        self.send_data(0xF7)
        self.wait_until_idle()
        
        self.send_command(0x47)  # Auto Write B/W RAM
        self.send_data(0xF7)
        self.wait_until_idle()
        
        # More initialization commands...
        # These would typically match the manufacturer's code
        
        self.initialized = True
        logger.info("Display initialized successfully")

    def getbuffer(self, image):
        """Get buffer for standard black/white mode (similar to manufacturer's method)"""
        buf = [0xFF] * (self.WIDTH * self.HEIGHT // 8)
        
        # Convert image to black and white
        if image.mode != '1':
            image = image.convert('1')
        
        # Resize image if needed
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
            
        # Convert image to buffer format
        pixels = image.load()
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if pixels[x, y] == 0:  # Black pixel
                    buf[(x + y * self.WIDTH) // 8] &= ~(0x80 >> (x % 8))
                    
        return buf
        
    def getbuffer_4Gray(self, image):
        """Get buffer for 4-level grayscale mode (similar to manufacturer's method)"""
        # Convert to grayscale if not already
        if image.mode != 'L':
            image = image.convert('L')
            
        # Resize if needed
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        
        # Create buffers for the 4 gray levels (as in manufacturer's example)
        buf_0 = [0xFF] * (self.WIDTH * self.HEIGHT // 8)  # black
        buf_1 = [0xFF] * (self.WIDTH * self.HEIGHT // 8)  # dark gray
        buf_2 = [0xFF] * (self.WIDTH * self.HEIGHT // 8)  # light gray
        buf_3 = [0xFF] * (self.WIDTH * self.HEIGHT // 8)  # white
        
        pixels = image.load()
        
        # Process pixel data to 4 gray level buffers
        for y in range(0, self.HEIGHT):
            for x in range(0, self.WIDTH):
                if pixels[x, y] >= 192:  # white
                    pass
                elif pixels[x, y] >= 128:  # light gray
                    buf_0[(x + y * self.WIDTH) // 8] &= ~(0x80 >> (x % 8))
                elif pixels[x, y] >= 64:  # dark gray
                    buf_1[(x + y * self.WIDTH) // 8] &= ~(0x80 >> (x % 8))
                else:  # black
                    buf_2[(x + y * self.WIDTH) // 8] &= ~(0x80 >> (x % 8))
                    
        return buf_0 + buf_1 + buf_2 + buf_3

    def display_4Gray(self, image):
        """Display 4-level grayscale image (similar to manufacturer's example)"""
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
            
        logger.info("Displaying 4-level grayscale image")
        
        # If image is a buffer, use it directly
        if isinstance(image, (list, bytearray)):
            buf = image
        else:
            # Otherwise process the image to get the buffer
            buf = self.getbuffer_4Gray(image)
        
        if self.hardware_available:
            self.send_command(0x24)  # WRITE_RAM
            for i in range(0, self.WIDTH * self.HEIGHT // 8):
                self.send_data(buf[i])
                
            self.send_command(0x26)  # WRITE_RAM2
            for i in range(self.WIDTH * self.HEIGHT // 8, self.WIDTH * self.HEIGHT // 8 * 2):
                self.send_data(buf[i])
                
            self.send_command(0x20)  # DISPLAY_REFRESH
            self.wait_until_idle()
        else:
            logger.info("Simulated display in mock mode")

    def display_image(self, image):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Displaying image on e-Paper display.")

        if image.mode != '1':
            image = image.convert('1')
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))

        # Convert to buffer format and display
        buffer = self.getbuffer(image)
        
        if self.hardware_available:
            self.send_command(0x24)  # WRITE_RAM
            for byte in buffer:
                self.send_data(byte)
                
            self.send_command(0x20)  # DISPLAY_REFRESH
            self.wait_until_idle()
        else:
            logger.info(f"Would display image with size {image.size} on e-Paper (mock mode)")

    def reset(self):
        logger.debug("Resetting e-Paper display.")
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.1)
        self.GPIO.output(self.RST_PIN, self.GPIO.LOW)
        time.sleep(0.1)
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.1)

    def send_command(self, command):
        self.GPIO.output(self.DC_PIN, self.GPIO.LOW)
        self.GPIO.output(self.CS_PIN, self.GPIO.LOW)
        self.SPI.writebytes([command])
        self.GPIO.output(self.CS_PIN, self.GPIO.HIGH)

    def send_data(self, data):
        self.GPIO.output(self.DC_PIN, self.GPIO.HIGH)
        self.GPIO.output(self.CS_PIN, self.GPIO.LOW)
        if isinstance(data, int):
            data = [data]
        self.SPI.writebytes(data)
        self.GPIO.output(self.CS_PIN, self.GPIO.HIGH)

    def wait_until_idle(self):
        logger.debug("Waiting for e-Paper display to become idle.")
        while self.GPIO.input(self.BUSY_PIN) == 0:
            time.sleep(0.1)
        logger.debug("Display is now idle.")

    def clear(self):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Clearing e-Paper display.")
        self.send_command(0x10)
        for _ in range(self.WIDTH * self.HEIGHT // 8):
            self.send_data(0xFF)
        self.send_command(0x12)
        self.wait_until_idle()

    def display_bytes(self, image_bytes):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Displaying raw byte data on e-Paper display.")

        if len(image_bytes) != self.WIDTH * self.HEIGHT // 8:
            raise ValueError("Incorrect byte array size for display.")

        self.send_command(0x10)
        for byte in image_bytes:
            self.send_data(byte)
        self.send_command(0x12)
        self.wait_until_idle()

    def sleep(self):
        logger.info("Putting e-Paper display to sleep.")
        self.send_command(0x02)
        self.wait_until_idle()
        self.send_command(0x07)
        self.send_data(0xA5)

    def __del__(self):
        try:
            if hasattr(self, 'SPI') and hasattr(self.SPI, 'close'):
                self.SPI.close()
            logger.info("Cleaned up SPI and GPIO.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
