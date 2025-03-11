from utils.logger import logger
from PIL import Image
import time
import numpy as np
import os
import traceback
from devices.eink.eink import EInkDeviceInterface

# Mock implementations for testing
class MockSpiDev:
    def __init__(self, bus=0, device=0):
        self.bus = bus
        self.device = device
        self.max_speed_hz = 0
        logger.debug(f"Mock SPI initialized on bus {bus}, device {device}")
    
    def writebytes(self, data):
        logger.debug(f"Mock SPI write: {data[:10]}{'...' if len(data) > 10 else ''}")
    
    def close(self):
        logger.debug("Mock SPI closed")

# Enum-like classes for when gpiod is not available
class MockValue:
    ACTIVE = 1
    INACTIVE = 0

class MockDirection:
    INPUT = 0
    OUTPUT = 1
    AS_IS = 2

class Driver(EInkDeviceInterface):
    # Class variables
    width = 480
    height = 280
    
    def __init__(self):
        self.initialized = False
        self.USE_HARDWARE = False  # Initialize as False by default
        
        # GPIO pin definitions
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8
        
        # Default to mock values
        self.Value = MockValue
        self.Direction = MockDirection
        
        # Try to import Pi 5 compatible libraries
        try:
            import spidev
            import gpiod
            from gpiod.line import Value, Direction, Edge, Bias
            
            # Check if SPI device exists
            spi_device_path = '/dev/spidev0.0'
            logger.info(f"Checking for SPI device at {spi_device_path}")
            if not os.path.exists(spi_device_path):
                logger.error(f"SPI device {spi_device_path} not found! Make sure SPI is enabled.")
                logger.info("Available devices in /dev: " + str([f for f in os.listdir('/dev') if f.startswith('spi')]))
                raise FileNotFoundError(f"{spi_device_path} not found")
                
            # Check if GPIO chip exists
            gpio_chip_path = '/dev/gpiochip0'
            logger.info(f"Checking for GPIO device at {gpio_chip_path}")
            if not os.path.exists(gpio_chip_path):
                logger.error(f"GPIO device {gpio_chip_path} not found!")
                raise FileNotFoundError(f"{gpio_chip_path} not found")
                
            # Check permissions
            logger.info(f"Checking permissions for user {os.getuid()}")
            logger.info(f"SPI device permissions: {oct(os.stat(spi_device_path).st_mode)}")
            logger.info(f"GPIO device permissions: {oct(os.stat(gpio_chip_path).st_mode)}")
                
            self.USE_HARDWARE = True
            logger.info("Using Pi 5 compatible GPIO (gpiod) and SPI")
            
            # Initialize SPI
            logger.info("Opening SPI device")
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 2000000
            
            # Store for later use in init()
            self.Direction = Direction
            self.Value = Value
            self.Edge = Edge
            self.Bias = Bias

            logger.info("Hardware initialized successfully")
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            if hasattr(self, 'spi') and not isinstance(self.spi, MockSpiDev):
                try:
                    self.spi.close()
                except:
                    pass
            self.USE_HARDWARE = False
            self.spi = MockSpiDev()
    
    def init(self):
        logger.info("Initializing Waveshare 3.7in e-Paper HAT (Pi 5 compatible).")
        
        if self.USE_HARDWARE:
            try:
                import gpiod
                from gpiod.line_settings import LineSettings
                
                # Configure GPIO lines using gpiod 2.3.0 API
                logger.info("Requesting GPIO lines using gpiod 2.3.0 API")
                
                # Check if any existing requests need to be released
                if hasattr(self, 'reset_request'):
                    logger.info("Releasing previous reset line request")
                    self.reset_request.release()
                
                if hasattr(self, 'dc_request'):
                    logger.info("Releasing previous dc line request")
                    self.dc_request.release()
                    
                if hasattr(self, 'busy_request'):
                    logger.info("Releasing previous busy line request")
                    self.busy_request.release()
                
                if hasattr(self, 'chip'):
                    logger.info("Closing previous chip")
                    self.chip.close()
                
                # Open the chip
                logger.info("Opening GPIO chip")
                self.chip = gpiod.Chip('/dev/gpiochip0')
                
                # Create settings for output and input pins
                output_settings = LineSettings(direction=self.Direction.OUTPUT)
                input_settings = LineSettings(direction=self.Direction.INPUT)

                # Request each line individually with the correct settings
                logger.info(f"Requesting reset pin {self.reset_pin} as output")
                try:
                    self.reset_request = self.chip.request_lines(
                        {self.reset_pin: output_settings}, 
                        consumer="totem-reset"
                    )
                except OSError as e:
                    # If device is busy, try to check if it's already being used
                    if "Device or resource busy" in str(e):
                        logger.warning(f"Reset pin {self.reset_pin} is busy. Another process may be using it.")
                        # We'll continue and try the other pins
                    else:
                        raise
                
                logger.info(f"Requesting dc pin {self.dc_pin} as output")
                try:
                    self.dc_request = self.chip.request_lines(
                        {self.dc_pin: output_settings}, 
                        consumer="totem-dc"
                    )
                except OSError as e:
                    if "Device or resource busy" in str(e):
                        logger.warning(f"DC pin {self.dc_pin} is busy. Another process may be using it.")
                    else:
                        raise
                
                logger.info(f"Requesting busy pin {self.busy_pin} as input")
                try:
                    self.busy_request = self.chip.request_lines(
                        {self.busy_pin: input_settings}, 
                        consumer="totem-busy"
                    )
                except OSError as e:
                    if "Device or resource busy" in str(e):
                        logger.warning(f"Busy pin {self.busy_pin} is busy. Another process may be using it.")
                    else:
                        raise
                
                # Note: We're not requesting the CS pin as it's controlled by the SPI hardware
                logger.info(f"Using hardware CS on pin {self.cs_pin} (managed by SPI driver)")
                
                # Check if all required requests were successful - CS is no longer required
                if (hasattr(self, 'reset_request') and 
                    hasattr(self, 'dc_request') and 
                    hasattr(self, 'busy_request')):
                    # Reset the display
                    self.reset()
                    self.initialized = True
                    logger.info("Pi 5 e-Paper initialization complete")
                else:
                    logger.warning("Some required GPIO pins could not be requested. Falling back to mock mode.")
                    self.initialized = False
                    self.USE_HARDWARE = False
            except Exception as e:
                logger.error(f"Error initializing Pi 5 GPIO: {e}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                self.initialized = False
                self.USE_HARDWARE = False
        else:
            # Mock initialization
            logger.info("Mock initialization complete")
            self.initialized = True
    
    def reset(self):
        if self.USE_HARDWARE:
            try:
                logger.debug("Resetting display")
                self.reset_request.set_values({self.reset_pin: self.Value.ACTIVE})
                time.sleep(0.2)
                self.reset_request.set_values({self.reset_pin: self.Value.INACTIVE})
                time.sleep(0.2)
                self.reset_request.set_values({self.reset_pin: self.Value.ACTIVE})
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"Error during reset: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.debug("Mock reset")
            time.sleep(0.6)
    
    def send_command(self, command):
        if self.USE_HARDWARE:
            try:
                self.dc_request.set_values({self.dc_pin: self.Value.INACTIVE})  # Command mode
                # CS is handled automatically by the SPI driver
                self.spi.writebytes([command])
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.debug(f"Mock send command: {command}")
    
    def send_data(self, data):
        if self.USE_HARDWARE:
            try:
                self.dc_request.set_values({self.dc_pin: self.Value.ACTIVE})  # Data mode
                # CS is handled automatically by the SPI driver
                
                if isinstance(data, int):
                    self.spi.writebytes([data])
                else:
                    # Send data in chunks to avoid overflow
                    chunk_size = 1024  # Safe chunk size
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i + chunk_size]
                        self.spi.writebytes(chunk)
                        # Small delay between chunks to avoid overwhelming the SPI bus
                        time.sleep(0.001)
            except Exception as e:
                logger.error(f"Error sending data: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.debug(f"Mock send data: {data if isinstance(data, int) else '(data array)'}")
    
    def wait_until_idle(self):
        if self.USE_HARDWARE:
            try:
                logger.debug("Waiting for display to be idle")
                busy_values = self.busy_request.get_values()
                # Check if we have any values returned
                if busy_values:
                    # For gpiod 2.x, busy_values might be a list with a single value
                    busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(self.busy_pin)
                    while busy_value == self.Value.ACTIVE:
                        time.sleep(0.1)
                        busy_values = self.busy_request.get_values()
                        busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(self.busy_pin)
                else:
                    # If we can't read the busy pin, just wait a fixed time
                    logger.warning("Could not read busy pin, waiting fixed time instead")
                    time.sleep(1.0)
            except Exception as e:
                logger.error(f"Error waiting for idle: {e}")
                logger.error(traceback.format_exc())
                # Still wait a bit in case of error
                time.sleep(1.0)
        else:
            logger.debug("Mock wait until idle")
            time.sleep(0.5)
    
    def clear(self):
        logger.info("Clearing e-Paper display")
        if self.USE_HARDWARE and hasattr(self, 'dc_request') and hasattr(self, 'busy_request'):
            try:
                # Clear display - simple implementation
                self.send_command(0x10)  # Deep sleep
                time.sleep(0.1)
                self.send_command(0x04)  # Power on
                self.wait_until_idle()
            except Exception as e:
                logger.error(f"Error clearing display: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.info("Mock clear display")
    
    def display_image(self, image):
        logger.info("Displaying image on e-Paper display")
        if self.USE_HARDWARE:
            # Format image
            if image.mode != '1':
                image = image.convert('1')
            
            if image.size[0] != self.width or image.size[1] != self.height:
                image = image.resize((self.width, self.height))
            
            # Convert to byte array
            pixels = np.array(image)
            buffer = np.packbits(1 - pixels).tolist()
            
            # Send to display
            self.send_command(0x13)  # Data transmission 2
            self.send_data(buffer)
            
            # Refresh display
            self.send_command(0x12)
            time.sleep(0.1)
            self.wait_until_idle()
        else:
            logger.info(f"Mock display image with size {image.size}")
    
    def display_bytes(self, image_bytes):
        logger.info("Displaying raw bytes on e-Paper display")
        if self.USE_HARDWARE:
            self.send_command(0x13)  # Data transmission 2
            self.send_data(list(image_bytes))
            
            # Refresh display
            self.send_command(0x12)
            time.sleep(0.1)
            self.wait_until_idle()
        else:
            logger.info("Mock display bytes")
    
    def sleep(self):
        logger.info("Putting e-Paper to sleep")
        if self.USE_HARDWARE:
            self.send_command(0x02)  # Power off
            self.wait_until_idle()
            self.send_command(0x07)  # Deep sleep
            self.send_data(0xA5)
        else:
            logger.info("Mock sleep")
    
    def __del__(self):
        logger.info("Cleaning up e-Paper resources")
        if hasattr(self, 'spi') and not isinstance(self.spi, MockSpiDev):
            self.spi.close()
        
        if hasattr(self, 'USE_HARDWARE') and self.USE_HARDWARE and hasattr(self, 'chip'):
            # Cleanup GPIO
            if hasattr(self, 'reset_request'):
                self.reset_request.release()
            if hasattr(self, 'dc_request'):
                self.dc_request.release()
            if hasattr(self, 'busy_request'):
                self.busy_request.release()
            # No need to release cs_request as we're no longer requesting it 