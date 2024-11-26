from devices.eink.eink import EInkDeviceInterface
from utils.logger import logger
import spidev
import RPi.GPIO as GPIO
from PIL import Image
import time
import numpy as np

class Driver(EInkDeviceInterface):
    
     __init__(self):
        self.width = 480
        self.height = 280
        self.initialized = False

        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8

        self.spi = spidev.SpiDev(0, 0)
        self.spi.max_speed_hz = 2000000
    
     init(self):
        logger.info("Initializing Waveshare 3.7in e-Paper HAT.")
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_pin, GPIO.OUT)
        GPIO.setup(self.dc_pin, GPIO.OUT)
        GPIO.setup(self.busy_pin, GPIO.IN)
        GPIO.setup(self.cs_pin, GPIO.OUT)

        self.reset()
        self.initialized = True
        logger.info("Initialization complete.")

    
     reset(self):
        logger.debug("Resetting e-Paper display.")
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.1)

    
     send_command(self, command):
        GPIO.output(self.dc_pin, GPIO.LOW)
        GPIO.output(self.cs_pin, GPIO.LOW)
        self.spi.writebytes([command])
        GPIO.output(self.cs_pin, GPIO.HIGH)

    
     send_data(self, data):
        GPIO.output(self.dc_pin, GPIO.HIGH)
        GPIO.output(self.cs_pin, GPIO.LOW)
        if isinstance(data, int):
            data = [data]
        self.spi.writebytes(data)
        GPIO.output(self.cs_pin, GPIO.HIGH)

    
     wait_until_idle(self):
        logger.debug("Waiting for e-Paper display to become idle.")
        while GPIO.input(self.busy_pin) == 0:
            time.sleep(0.1)
        logger.debug("Display is now idle.")

    
     clear(self):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Clearing e-Paper display.")
        self.send_command(0x10)
        for _ in range(self.width * self.height // 8):
            self.send_data(0xFF)
        self.send_command(0x12)
        self.wait_until_idle()

    
     display_image(self, image):
        if not self.initialized:
            raise RuntimeError("Display not initialized.")
        logger.info("Displaying image on e-Paper display.")

        image = image.convert('1')
        image = image.resize((self.width, self.height))

        image_data = np.array(image)
        image_data = np.packbits(np.fliplr(image_data), axis=1)
        image_bytes = image_data.flatten().tolist()

        self.send_command(0x10)
        for byte in image_bytes:
            self.send_data(byte)
        self.send_command(0x12)
        self.wait_until_idle()

    
     display_bytes(self, image_bytes):
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

    
     sleep(self):
        logger.info("Putting e-Paper display to sleep.")
        self.send_command(0x02)
        self.wait_until_idle()
        self.send_command(0x07)
        self.send_data(0xA5)

    
     __del__(self):
        try:
            self.spi.close()
            GPIO.cleanup()
            logger.info("Cleaned up SPI and GPIO.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
