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
    
    def __init__(self):
        self.width = self.WIDTH
        self.height = self.HEIGHT
        self.initialized = False

        # Define GPIO pin connections
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8

        # Init SPI
        self.spi = spidev() if isinstance(spidev, type) else spidev.SpiDev(0, 0)
        if hasattr(self.spi, 'max_speed_hz'):
            self.spi.max_speed_hz = 2000000  # 2MHz
    
    def init(self):
        logger.info("Initializing Waveshare 2.13in e-Paper HAT.")
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.reset_pin, GPIO.OUT)
        GPIO.setup(self.dc_pin, GPIO.OUT)
        GPIO.setup(self.busy_pin, GPIO.IN)
        GPIO.setup(self.cs_pin, GPIO.OUT)
        
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
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.2)

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
        while GPIO.input(self.busy_pin) == 0:  # 0: busy, 1: idle
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
        if not self.initialized:
            self.init()
            
        logger.info("Displaying image on e-Paper display.")

        # Process image
        if image.mode != '1':
            image = image.convert('1')
        
        if image.size[0] != self.width or image.size[1] != self.height:
            image = image.resize((self.width, self.height))

        # Get image data
        pixels = np.array(image)
        buffer = np.packbits(~pixels.astype(bool)).tolist()  # Invert: 0 = black, 1 = white
        
        # Set window and cursor
        self._set_window(0, 0, self.width-1, self.height-1)
        self._set_cursor(0, 0)
        
        # Send data
        self.send_command(self.WRITE_RAM)
        self.send_data(buffer)
        
        # Update display
        self._update()

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
            if hasattr(self, 'spi') and hasattr(self.spi, 'close'):
                self.spi.close()
            logger.info("Cleaned up SPI and GPIO.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}") 