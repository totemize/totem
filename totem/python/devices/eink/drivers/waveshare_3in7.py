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
    def __init__(self):
        self.width = 480
        self.height = 280
        self.initialized = False

        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8

        self.spi = spidev() if isinstance(spidev, type) else spidev.SpiDev(0, 0)
        if hasattr(self.spi, 'max_speed_hz'):
            self.spi.max_speed_hz = 2000000
    
    def init(self):
        logger.info("Initializing Waveshare 3.7in e-Paper HAT.")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_pin, GPIO.OUT)
        GPIO.setup(self.dc_pin, GPIO.OUT)
        GPIO.setup(self.busy_pin, GPIO.IN)
        GPIO.setup(self.cs_pin, GPIO.OUT)

        self.reset()
        self.initialized = True
        logger.info("Initialization complete.")

    def reset(self):
        logger.debug("Resetting e-Paper display.")
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.1)

    def send_command(self, command):
        GPIO.output(self.dc_pin, GPIO.LOW)
        GPIO.output(self.cs_pin, GPIO.LOW)
        self.spi.writebytes([command])
        GPIO.output(self.cs_pin, GPIO.HIGH)

    def send_data(self, data):
        GPIO.output(self.dc_pin, GPIO.HIGH)
        GPIO.output(self.cs_pin, GPIO.LOW)
        if isinstance(data, int):
            data = [data]
        self.spi.writebytes(data)
        GPIO.output(self.cs_pin, GPIO.HIGH)

    def wait_until_idle(self):
        logger.debug("Waiting for e-Paper display to become idle.")
        while GPIO.input(self.busy_pin) == 0:
            time.sleep(0.1)
        logger.debug("Display is now idle.")

    def clear(self):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Clearing e-Paper display.")
        self.send_command(0x10)
        for _ in range(self.width * self.height // 8):
            self.send_data(0xFF)
        self.send_command(0x12)
        self.wait_until_idle()

    def display_image(self, image):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Displaying image on e-Paper display.")

        image = image.convert('1')
        image = image.resize((self.width, self.height))

        # In mock mode, we'll just log information about the image
        logger.info(f"Would display image with size {image.size} on e-Paper")
        
        try:
            # Only process the image if we can import numpy
            import numpy as np
            image_data = np.array(image)
            image_data = np.packbits(~(image_data.astype(bool)), axis=1)
            image_bytes = image_data.flatten().tolist()
            
            self.send_command(0x10)
            for byte in image_bytes:
                self.send_data(byte)
            self.send_command(0x12)
            self.wait_until_idle()
        except ImportError:
            logger.warning("NumPy not available, skipping actual display")
            self.send_command(0x10)
            # Just send some dummy data
            for _ in range(self.width * self.height // 8):
                self.send_data(0xFF)
            self.send_command(0x12)
            self.wait_until_idle()

    def display_bytes(self, image_bytes):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Displaying raw byte data on e-Paper display.")

        if len(image_bytes) != self.width * self.height // 8:
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
            if hasattr(self, 'spi') and hasattr(self.spi, 'close'):
                self.spi.close()
            logger.info("Cleaned up SPI and GPIO.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
