#!/usr/bin/env python3
"""
Waveshare 2.13inch E-Paper HAT Driver
Resolution: 250x122 pixels
Interface: SPI
Color: Black and White
"""

import os
import time
import logging
import sys
import traceback

# Add the parent directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))  # drivers directory
eink_dir = os.path.dirname(script_dir)  # eink directory
devices_dir = os.path.dirname(eink_dir)  # devices directory
python_dir = os.path.dirname(devices_dir)  # python directory
sys.path.insert(0, python_dir)

# Import logger first before using it
try:
    # Try totem package imports first
    from totem.python.utils.logger import logger
except ImportError:
    try:
        # Fall back to direct imports for testing
        from utils.logger import logger
    except ImportError as e:
        # Create a basic logger if all else fails
        logger = logging.getLogger("eink")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.error(f"Failed to import logger: {e}")

# Import our device interface
try:
    # Try totem package imports first
    from totem.python.devices.eink.eink import EInkDeviceInterface
except ImportError:
    try:
        # Fall back to direct imports for testing
        from devices.eink.eink import EInkDeviceInterface
    except ImportError as e:
        logger.error(f"Failed to import EInkDeviceInterface: {e}")
        logger.error(traceback.format_exc())
        raise ImportError(f"Failed to import required modules: {e}")

# Try to import optional dependencies
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available. Image display functions will be limited.")
    
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not available. Some operations may be slower.")

# For testing without hardware
class MockSpiDev:
    def __init__(self):
        pass
            
    def open(self, bus, device):
        logger.debug(f"Mock SPI opened on bus {bus}, device {device}")
            
    def max_speed_hz(self, speed):
        logger.debug(f"Mock SPI speed set to {speed}")
            
    def mode(self, mode):
        logger.debug(f"Mock SPI mode set to {mode}")
            
    def xfer2(self, data):
        logger.debug(f"Mock SPI data transfer: {len(data)} bytes")
        return [0] * len(data)
            
    def writebytes(self, data):
        logger.debug(f"Mock SPI writebytes: {len(data)} bytes")
            
    def close(self):
        logger.debug("Mock SPI closed")
    
class MockGPIO:
    BOARD = 1
    BCM = 0  # Add BCM mode
    OUT = 2
    IN = 3
    HIGH = 1
    LOW = 0
        
    @staticmethod
    def setmode(mode):
        logger.debug(f"Mock GPIO mode set to {mode}")
            
    @staticmethod
    def setup(pin, mode):
        logger.debug(f"Mock GPIO setup pin {pin} as {'output' if mode == MockGPIO.OUT else 'input'}")
            
    @staticmethod
    def output(pin, value):
        logger.debug(f"Mock GPIO output pin {pin} set to {value}")
            
    @staticmethod
    def input(pin):
        logger.debug(f"Mock GPIO input from pin {pin}")
        return 1
            
    @staticmethod
    def cleanup():
        logger.debug("Mock GPIO cleanup")
            
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
    """
    Driver for Waveshare 2.13inch e-Paper HAT
    Resolution: 250x122 pixels
    Interface: SPI
    Color: Black and White
    """
    # Constants for the display
    WIDTH = 250
    HEIGHT = 122
    
    # Display commands
    DRIVER_OUTPUT_CONTROL                  = 0x01
    BOOSTER_SOFT_START_CONTROL             = 0x0C
    GATE_SCAN_START_POSITION               = 0x0F
    DEEP_SLEEP_MODE                        = 0x10
    DATA_ENTRY_MODE_SETTING                = 0x11
    SW_RESET                               = 0x12
    TEMPERATURE_SENSOR_CONTROL             = 0x1A
    MASTER_ACTIVATION                      = 0x20
    DISPLAY_UPDATE_CONTROL_1               = 0x21
    DISPLAY_UPDATE_CONTROL_2               = 0x22
    WRITE_RAM                              = 0x24
    WRITE_VCOM_REGISTER                    = 0x2C
    WRITE_LUT_REGISTER                     = 0x32
    SET_DUMMY_LINE_PERIOD                  = 0x3A
    SET_GATE_TIME                          = 0x3B
    BORDER_WAVEFORM_CONTROL                = 0x3C
    SET_RAM_X_ADDRESS_START_END_POSITION   = 0x44
    SET_RAM_Y_ADDRESS_START_END_POSITION   = 0x45
    SET_RAM_X_ADDRESS_COUNTER              = 0x4E
    SET_RAM_Y_ADDRESS_COUNTER              = 0x4F
    TERMINATE_FRAME_READ_WRITE             = 0xFF
    
    # Properties to match EInk interface
    width = WIDTH
    height = HEIGHT
    
    def __init__(self):
        self.initialized = False
        self.hardware_available = False  # Initialize hardware availability flag
        
        # Try to import hardware libraries with proper error handling
        try:
            import RPi.GPIO as GPIO
            import spidev
            self.GPIO = GPIO
            self.SPI = spidev.SpiDev()
            self.hardware_available = True
            logger.info("Hardware libraries loaded successfully")
        except ImportError:
            logger.warning("Hardware libraries not available, using mock mode")
            self.GPIO = MockGPIO
            self.SPI = MockSpiDev()
            self.hardware_available = False
            
        # Display dimensions
        self.width = self.WIDTH
        self.height = self.HEIGHT

        # Define GPIO pin connections for Waveshare 2.13inch E-Paper HAT 
        # These pins are standard for the HAT
        self.reset_pin = 17  # Physical pin 11
        self.dc_pin = 25     # Physical pin 22
        self.busy_pin = 24   # Physical pin 18
        self.cs_pin = 8      # Physical pin 24
        
    def init(self):
        """Initialize the display"""
        logger.info("Initializing Waveshare 2.13in e-Paper HAT.")
        
        try:
            # Initialize GPIO
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.reset_pin, self.GPIO.OUT)
            self.GPIO.setup(self.dc_pin, self.GPIO.OUT)
            self.GPIO.setup(self.busy_pin, self.GPIO.IN)
            
            # Initialize SPI if hardware is available
            if self.hardware_available:
                try:
                    # Initialize SPI
                    self.SPI.open(0, 0)  # Bus 0, Device 0
                    self.SPI.max_speed_hz = 2000000  # 2MHz
                    self.SPI.mode = 0b00  # Mode 0
                    logger.info("SPI interface initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize SPI: {e}")
                    self.hardware_available = False
                    self.SPI = MockSpiDev()
                    logger.warning("Falling back to mock SPI implementation")
            
            # Reset the display
            self.reset()
            
            # Send initialization commands
            self.send_command(self.DRIVER_OUTPUT_CONTROL)
            self.send_data(0xF9)  # (HEIGHT-1) & 0xFF
            self.send_data(0x00)  # ((HEIGHT-1) >> 8) & 0xFF
            self.send_data(0x00)  # GD = 0, SM = 0, TB = 0
            
            self.send_command(self.BOOSTER_SOFT_START_CONTROL)
            self.send_data(0xD7)
            self.send_data(0xD6)
            self.send_data(0x9D)
            
            self.send_command(self.WRITE_VCOM_REGISTER)
            self.send_data(0xA8)  # VCOM 7C
            
            self.send_command(self.SET_DUMMY_LINE_PERIOD)
            self.send_data(0x1A)  # 4 dummy lines per gate
            
            self.send_command(self.SET_GATE_TIME)
            self.send_data(0x08)  # 2us per line
            
            self.send_command(self.DATA_ENTRY_MODE_SETTING)
            self.send_data(0x03)  # X increment; Y increment
            
            # Set the look-up table for full refresh
            self._set_lut()
            
            self.initialized = True
            logger.info("Initialization complete.")
            
        except Exception as e:
            logger.error(f"Failed to initialize display: {e}")
            logger.error(traceback.format_exc())
            self.hardware_available = False
            self.initialized = False
            raise

    def _set_lut(self):
        """Set the look-up table for display refresh"""
        # LUT for full refresh
        lut_full_update = [
            0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E,
            0x01, 0x00, 0x00, 0x00, 0x00, 0x00
        ]
        
        self.send_command(self.WRITE_LUT_REGISTER)
        for i in range(30):
            self.send_data(lut_full_update[i])

    def reset(self):
        logger.debug("Resetting e-Paper display.")
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        time.sleep(0.2)
        self.GPIO.output(self.reset_pin, self.GPIO.LOW)
        time.sleep(0.2)
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        time.sleep(0.2)

    def send_command(self, command):
        self.GPIO.output(self.dc_pin, self.GPIO.LOW)
        if hasattr(self.SPI, 'writebytes'):
            self.SPI.writebytes([command])
        else:
            self.SPI.xfer2([command])

    def send_data(self, data):
        self.GPIO.output(self.dc_pin, self.GPIO.HIGH)
        if isinstance(data, int):
            data = [data]
        if hasattr(self.SPI, 'writebytes'):
            self.SPI.writebytes(data)
        else:
            self.SPI.xfer2(data)

    def wait_until_idle(self):
        logger.debug("Waiting for e-Paper display to become idle.")
        while self.GPIO.input(self.busy_pin) == 0:  # 0: busy, 1: idle
            time.sleep(0.1)
        logger.debug("Display is now idle.")

    def _set_window(self, x_start, y_start, x_end, y_end):
        """Set window for data transmission"""
        self.send_command(self.SET_RAM_X_ADDRESS_START_END_POSITION)
        # X start
        self.send_data((x_start >> 3) & 0xFF)
        # X end
        self.send_data((x_end >> 3) & 0xFF)
        
        self.send_command(self.SET_RAM_Y_ADDRESS_START_END_POSITION)
        # Y start
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        # Y end
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    def _set_cursor(self, x, y):
        """Set cursor position for data transmission"""
        self.send_command(self.SET_RAM_X_ADDRESS_COUNTER)
        self.send_data((x >> 3) & 0xFF)
        
        self.send_command(self.SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)

    def clear(self):
        if not self.initialized:
            self.init()
            
        logger.info("Clearing e-Paper display.")
        
        # Set window and cursor
        self._set_window(0, 0, self.width-1, self.height-1)
        self._set_cursor(0, 0)
        
        # Send write RAM command
        self.send_command(self.WRITE_RAM)
        
        # Send all white pixels
        for _ in range(int(self.width * self.height / 8)):
            self.send_data(0xFF)  # 0xFF = white
            
        self._update()
        
    def _update(self):
        """Update the display"""
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC4)
        self.send_command(self.MASTER_ACTIVATION)
        self.send_command(self.TERMINATE_FRAME_READ_WRITE)
        self.wait_until_idle()

    def display_image(self, image):
        """
        Display an image on the e-Paper display
        Args:
            image: PIL Image object
        """
        if not PIL_AVAILABLE:
            logger.error("PIL is not available. Cannot display image.")
            return False
        
        logger.info("Displaying image on e-Paper display")
        if self.hardware_available:
            # Convert image to 1-bit black and white
            if image.mode != '1':
                image = image.convert('1')
            
            # Resize image to fit the display if needed
            if image.size != (self.WIDTH, self.HEIGHT):
                image = image.resize((self.WIDTH, self.HEIGHT))
            
            # Convert to bytes and send to display
            buf = bytearray(self.WIDTH * self.HEIGHT // 8)
            for y in range(self.HEIGHT):
                for x in range(self.WIDTH):
                    if image.getpixel((x, y)) == 0:  # Black pixel
                        buf[(x + y * self.WIDTH) // 8] |= 0x80 >> (x % 8)
            
            self.display_bytes(buf)
            return True
        else:
            logger.info(f"Mock display image with size {image.size}")
            return True

    def display_bytes(self, image_bytes):
        if not self.initialized:
            self.init()
            
        logger.info("Displaying raw byte data on e-Paper display.")

        if len(image_bytes) != int(self.width * self.height / 8):
            raise ValueError(f"Incorrect byte array size for display. Expected {int(self.width * self.height / 8)} bytes, got {len(image_bytes)}.")

        # Set window and cursor
        self._set_window(0, 0, self.width-1, self.height-1)
        self._set_cursor(0, 0)
        
        # Send data
        self.send_command(self.WRITE_RAM)
        self.send_data(list(image_bytes))
        
        # Update display
        self._update()

    def sleep(self):
        logger.info("Putting e-Paper display to sleep.")
        self.send_command(self.DEEP_SLEEP_MODE)
        self.send_data(0x01)  # Enter deep sleep
        
    def __del__(self):
        try:
            # Close SPI connection if it exists
            if hasattr(self, 'SPI') and self.SPI is not None:
                if hasattr(self.SPI, 'close'):
                    self.SPI.close()
            
            # Clean up GPIO
            if hasattr(self, 'GPIO') and hasattr(self.GPIO, 'cleanup'):
                # Only clean up our pins to avoid interfering with other parts of the system
                try:
                    pins = [self.reset_pin, self.dc_pin, self.busy_pin, self.cs_pin]
                    for pin in pins:
                        self.GPIO.cleanup(pin)
                except:
                    # If pin-specific cleanup fails, fall back to general cleanup
                    self.GPIO.cleanup()
            
            logger.info("Cleaned up SPI and GPIO.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.error(traceback.format_exc())

    def getbuffer(self, image):
        """Convert image to display buffer, similar to manufacturer's method"""
        if not PIL_AVAILABLE:
            logger.error("PIL is not available. Cannot process image.")
            return None
            
        # Convert to black and white
        if image.mode != '1':
            image = image.convert('1')
            
        # Resize if needed
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
            
        # Convert to buffer format
        buf = bytearray(self.WIDTH * self.HEIGHT // 8)
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if image.getpixel((x, y)) == 0:  # Black pixel
                    buf[(x + y * self.WIDTH) // 8] |= 0x80 >> (x % 8)
                    
        return buf
    
    def display(self, buffer):
        """Display method that matches manufacturer's API"""
        logger.info("Displaying buffer on e-Paper display")
        if isinstance(buffer, (bytearray, bytes, list)):
            # If buffer is already in bytes format, use it directly
            return self.display_bytes(buffer)
        else:
            # Otherwise, assume it's an image and convert it
            return self.display_image(buffer)
    
    def Clear(self, color):
        """Clear method that matches manufacturer's API"""
        logger.info(f"Clearing display with color {color}")
        self.clear() 