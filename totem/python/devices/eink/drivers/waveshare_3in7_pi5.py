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
        
        # Try to import Pi 5 compatible libraries
        try:
            import spidev
            import gpiod
            
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
            
            # Initialize GPIO using gpiod with full path
            logger.info("Opening GPIO chip with full path")
            self.chip = gpiod.Chip('/dev/gpiochip0')
            
            # For gpiod 2.x API, we use request_lines instead of individual lines
            # We'll defer line requests to init() method
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
                
                # Configure GPIO lines using gpiod 2.x API
                logger.info("Requesting GPIO lines using gpiod 2.x API")
                
                # Request output lines
                self.output_config = gpiod.LineConfig()
                self.output_config.direction = gpiod.Direction.OUTPUT
                
                # Request input lines
                self.input_config = gpiod.LineConfig()
                self.input_config.direction = gpiod.Direction.INPUT
                
                # Request reset and data/command lines as output
                logger.info(f"Requesting reset pin {self.reset_pin} and dc pin {self.dc_pin} as outputs")
                self.reset_request = self.chip.request_lines({
                    self.reset_pin: self.output_config
                }, consumer="totem-reset")
                
                self.dc_request = self.chip.request_lines({
                    self.dc_pin: self.output_config
                }, consumer="totem-dc")
                
                # Request busy line as input
                logger.info(f"Requesting busy pin {self.busy_pin} as input")
                self.busy_request = self.chip.request_lines({
                    self.busy_pin: self.input_config
                }, consumer="totem-busy")
                
                # Request chip select line as output
                logger.info(f"Requesting cs pin {self.cs_pin} as output")
                self.cs_request = self.chip.request_lines({
                    self.cs_pin: self.output_config
                }, consumer="totem-cs")
                
                # Reset the display
                self.reset()
                self.initialized = True
                logger.info("Pi 5 e-Paper initialization complete")
            except Exception as e:
                logger.error(f"Error initializing Pi 5 GPIO: {e}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                self.initialized = False
        else:
            # Mock initialization
            logger.info("Mock initialization complete")
            self.initialized = True
    
    def reset(self):
        if self.USE_HARDWARE:
            logger.debug("Resetting display")
            self.reset_request.set_values({self.reset_pin: 1})
            time.sleep(0.2)
            self.reset_request.set_values({self.reset_pin: 0})
            time.sleep(0.2)
            self.reset_request.set_values({self.reset_pin: 1})
            time.sleep(0.2)
        else:
            logger.debug("Mock reset")
            time.sleep(0.6)
    
    def send_command(self, command):
        if self.USE_HARDWARE:
            self.dc_request.set_values({self.dc_pin: 0})  # Command mode
            self.cs_request.set_values({self.cs_pin: 0})  # Chip select active
            self.spi.writebytes([command])
            self.cs_request.set_values({self.cs_pin: 1})  # Chip select inactive
        else:
            logger.debug(f"Mock send command: {command}")
    
    def send_data(self, data):
        if self.USE_HARDWARE:
            self.dc_request.set_values({self.dc_pin: 1})  # Data mode
            self.cs_request.set_values({self.cs_pin: 0})  # Chip select active
            
            if isinstance(data, int):
                self.spi.writebytes([data])
            else:
                self.spi.writebytes(data)
                
            self.cs_request.set_values({self.cs_pin: 1})  # Chip select inactive
        else:
            logger.debug(f"Mock send data: {data if isinstance(data, int) else '(data array)'}")
    
    def wait_until_idle(self):
        if self.USE_HARDWARE:
            logger.debug("Waiting for display to be idle")
            busy_values = self.busy_request.get_values()
            while busy_values[self.busy_pin] == 1:
                time.sleep(0.1)
                busy_values = self.busy_request.get_values()
        else:
            logger.debug("Mock wait until idle")
            time.sleep(0.5)
    
    def clear(self):
        logger.info("Clearing e-Paper display")
        if self.USE_HARDWARE:
            # Clear display - simple implementation
            self.send_command(0x10)  # Deep sleep
            time.sleep(0.1)
            self.send_command(0x04)  # Power on
            self.wait_until_idle()
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
            if hasattr(self, 'cs_request'):
                self.cs_request.release() 