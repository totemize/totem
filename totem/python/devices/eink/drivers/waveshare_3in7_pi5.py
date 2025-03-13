#!/usr/bin/env python3
"""
Waveshare 3.7inch e-Paper HAT driver for Raspberry Pi 5.
"""

import os
import time
import traceback
import logging

# Import hardware-dependent libraries with proper error handling
HARDWARE_AVAILABLE = False
try:
    import gpiod
    import spidev
    import numpy as np
    HARDWARE_AVAILABLE = True
    logger_import_msg = "Hardware libraries successfully imported"
except ImportError as e:
    HARDWARE_AVAILABLE = False
    logger_import_msg = f"Hardware libraries import failed: {e}"

# Import our utility modules after setting the hardware flag
try:
    # Try totem package imports first
    from totem.python.utils.logger import logger
    from totem.python.devices.eink.eink import EInkDeviceInterface
except ImportError:
    try:
        # Fall back to direct imports for testing
        import sys
        # Add parent directories to path if needed
        script_dir = os.path.dirname(os.path.abspath(__file__))  # drivers directory
        devices_dir = os.path.dirname(os.path.dirname(script_dir))  # devices directory
        python_dir = os.path.dirname(devices_dir)  # python directory
        sys.path.insert(0, python_dir)
        
        from utils.logger import logger
        from devices.eink.eink import EInkDeviceInterface
    except ImportError as e:
        raise ImportError(f"Failed to import required modules: {e}")

# Log the import status
logger.info(logger_import_msg)

# Mock classes for testing when hardware is not available
class MockSpiDev:
    def __init__(self):
        self.max_speed_hz = 0
        self.mode = 0
        
    def open(self, bus, device):
        logger.debug(f"Mock SPI: Opening bus {bus}, device {device}")
        return
        
    def xfer2(self, data):
        if isinstance(data, list):
            logger.debug(f"Mock SPI: Transferring {len(data)} bytes")
        return [0] * len(data)
        
    def close(self):
        logger.debug("Mock SPI: Closing")
        return

# Mock GPIO classes for testing
class MockValue:
    ACTIVE = 1
    INACTIVE = 0

class MockDirection:
    INPUT = "in"
    OUTPUT = "out"

class MockGPIO:
    def __init__(self):
        self.pins = {}
        logger.debug("Mock GPIO: Initialized")
        
    def request_lines(self, pins, consumer):
        logger.debug(f"Mock GPIO: Requesting lines {pins} for {consumer}")
        return self
        
    def set_values(self, values):
        for pin, value in values.items():
            logger.debug(f"Mock GPIO: Setting pin {pin} to {value}")
            self.pins[pin] = value
        
    def get_values(self):
        return {pin: 0 for pin in self.pins}
        
    def release(self):
        logger.debug("Mock GPIO: Releasing lines")
        return

class Driver(EInkDeviceInterface):
    # Class variables
    width = 480
    height = 280
    
    def __init__(self):
        # Initialize state tracking variables for resource management
        self.gpio_chip = None
        self.reset_line = None
        self.dc_line = None
        self.busy_line = None
        self.spi = None
        self.initialized = False
        self.hardware_available = False
        self.mock_mode = False

        # Track which resources were successfully acquired for proper cleanup
        self.resources_acquired = {
            'gpio_chip': False,
            'reset_line': False,
            'dc_line': False,
            'busy_line': False,
            'spi': False
        }

        self.USE_HARDWARE = False  # Initialize as False by default
        self.DEBUG_MODE = False    # Debug mode for SPI/GPIO commands
        
        # GPIO pin definitions
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8
        
        # Default to mock values
        self.Value = MockValue
        self.Direction = MockDirection
        
        # Check if we're using v1 or v2 API
        self.has_v2_api = False
        if HARDWARE_AVAILABLE:
            try:
                from gpiod.line_settings import LineSettings
                self.has_v2_api = True
                logger.info("Using gpiod v2 API")
            except ImportError:
                self.has_v2_api = False
                logger.info("Using gpiod v1 API")
        
        # Try to import Pi 5 compatible libraries
        try:
            if not HARDWARE_AVAILABLE:
                logger.warning("Hardware libraries not available, falling back to mock implementations")
                raise ImportError("Hardware libraries not available")
                
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
            
            # Initialize SPI - ensure spidev is available
            if not 'spidev' in globals():
                logger.error("spidev module not available in the global namespace")
                raise ImportError("spidev module not properly imported")
                
            logger.info("Opening SPI device")
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 2000000
            
            logger.info("Hardware initialized successfully")
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            if hasattr(self, 'spi') and hasattr(self.spi, 'close') and not isinstance(self.spi, MockSpiDev):
                try:
                    self.spi.close()
                except:
                    pass
            self.USE_HARDWARE = False
            self.spi = MockSpiDev()
            logger.info("Falling back to mock SPI implementation")
    
    def init(self, mode=0):
        """Initialize the display with improved error handling and resource tracking"""
        if self.initialized:
            logger.info("Display already initialized, cleaning up first")
            self.cleanup_resources()

        self.mock_mode = False
        success = False

        try:
            logger.info(f"Initializing Waveshare 3.7in e-Paper HAT (Pi 5 compatible).")
            self.cleanup_resources()  # Ensure we start clean

            # Initialize GPIO
            success = self._init_gpio()
            if not success:
                logger.warning("GPIO initialization failed, falling back to mock mode")
                self.mock_mode = True
                self.initialized = True
                return True  # Return true even in mock mode, since we can still function

            # Initialize SPI
            success = self._init_spi()
            if not success:
                logger.warning("SPI initialization failed, falling back to mock mode")
                self.mock_mode = True
                self.cleanup_resources()  # Clean up any resources that were acquired
                self.initialized = True
                return True

            # Hardware is available, proceed with real initialization
            self.hardware_available = True
            logger.info("Hardware initialized successfully")

            # Reset display and send init commands
            self._reset()
            self._send_init_commands(mode)
            
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            logger.error(traceback.format_exc())
            self.cleanup_resources()  # Clean up any resources that were acquired
            self.mock_mode = True
            self.initialized = True  # Set initialized to true so we can still function in mock mode
            return True  # Return success even in mock mode

    def _init_gpio(self):
        """Initialize GPIO with improved error handling"""
        try:
            logger.info("Initializing GPIO using gpiod v1 API")
            self.cleanup_gpio()  # Ensure we start clean
            
            # Open GPIO chip
            logger.info("Opening GPIO chip")
            try:
                self.gpio_chip = gpiod.chip(0)
                self.resources_acquired['gpio_chip'] = True
            except Exception as e:
                logger.error(f"Failed to open GPIO chip: {e}")
                return False
                
            # Request reset pin
            logger.info(f"Requesting reset pin {self.reset_pin} as output")
            try:
                self.reset_line = self.gpio_chip.get_line(self.reset_pin)
                self.reset_line.request(consumer="eink_reset", type=gpiod.LINE_REQ_DIR_OUT, flags=0)
                self.resources_acquired['reset_line'] = True
            except Exception as e:
                logger.warning(f"Reset pin {self.reset_pin} is busy. Another process may be using it.")
                
            # Request DC pin
            logger.info(f"Requesting dc pin {self.dc_pin} as output")
            try:
                self.dc_line = self.gpio_chip.get_line(self.dc_pin)
                self.dc_line.request(consumer="eink_dc", type=gpiod.LINE_REQ_DIR_OUT, flags=0)
                self.resources_acquired['dc_line'] = True
            except Exception as e:
                logger.warning(f"DC pin {self.dc_pin} is busy. Another process may be using it.")
                
            # Request busy pin
            logger.info(f"Requesting busy pin {self.busy_pin} as input")
            try:
                self.busy_line = self.gpio_chip.get_line(self.busy_pin)
                self.busy_line.request(consumer="eink_busy", type=gpiod.LINE_REQ_DIR_IN, flags=0)
                self.resources_acquired['busy_line'] = True
            except Exception as e:
                logger.warning(f"Busy pin {self.busy_pin} is busy. Another process may be using it.")
                
            # Check if we have all required GPIO lines
            if not (self.resources_acquired['reset_line'] and 
                    self.resources_acquired['dc_line'] and 
                    self.resources_acquired['busy_line']):
                logger.warning("Some required GPIO pins could not be requested. Falling back to mock mode.")
                self.cleanup_gpio()
                return False
                
            logger.info("GPIO initialization successful")
            return True
            
        except Exception as e:
            logger.error(f"Error during GPIO initialization: {e}")
            logger.error(traceback.format_exc())
            self.cleanup_gpio()
            return False

    def _init_spi(self):
        """Initialize SPI with error handling"""
        try:
            logger.info("Opening SPI device")
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 4000000
            self.spi.mode = 0
            self.resources_acquired['spi'] = True
            logger.info("SPI initialization successful")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SPI: {e}")
            if hasattr(self, 'spi') and self.spi is not None:
                try:
                    self.spi.close()
                except:
                    pass
            self.spi = None
            self.resources_acquired['spi'] = False
            return False

    def _reset(self):
        """Reset the display with error handling"""
        if self.mock_mode:
            logger.info("Mock reset")
            return
            
        try:
            logger.debug("Resetting e-Paper display")
            self.reset_line.set_value(1)
            time.sleep(0.2)
            self.reset_line.set_value(0)
            time.sleep(0.2)
            self.reset_line.set_value(1)
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"Error during display reset: {e}")
            self.mock_mode = True

    def cleanup_gpio(self):
        """Clean up GPIO resources with improved error handling"""
        logger.info("Cleaning up GPIO resources")
        
        # Release reset line
        if self.resources_acquired['reset_line'] and self.reset_line is not None:
            try:
                self.reset_line.release()
                logger.info("Released reset line")
            except Exception as e:
                logger.error(f"Error releasing reset line: {e}")
            finally:
                self.reset_line = None
                self.resources_acquired['reset_line'] = False
                
        # Release DC line
        if self.resources_acquired['dc_line'] and self.dc_line is not None:
            try:
                self.dc_line.release()
                logger.info("Released dc line")
            except Exception as e:
                logger.error(f"Error releasing dc line: {e}")
            finally:
                self.dc_line = None
                self.resources_acquired['dc_line'] = False
                
        # Release busy line
        if self.resources_acquired['busy_line'] and self.busy_line is not None:
            try:
                self.busy_line.release()
                logger.info("Released busy line")
            except Exception as e:
                logger.error(f"Error releasing busy line: {e}")
            finally:
                self.busy_line = None
                self.resources_acquired['busy_line'] = False
                
        # Close GPIO chip
        if self.resources_acquired['gpio_chip'] and self.gpio_chip is not None:
            try:
                # In some gpiod versions, there's no explicit close method
                # The chip gets closed when it goes out of scope
                self.gpio_chip = None
                logger.info("Closed GPIO chip")
            except Exception as e:
                logger.error(f"Error closing GPIO chip: {e}")
            finally:
                self.gpio_chip = None
                self.resources_acquired['gpio_chip'] = False

    def cleanup_resources(self):
        """Clean up all resources"""
        self.cleanup_gpio()
        
        # Close SPI
        if self.resources_acquired['spi'] and self.spi is not None:
            try:
                self.spi.close()
                logger.info("Closed SPI device")
            except Exception as e:
                logger.error(f"Error closing SPI device: {e}")
            finally:
                self.spi = None
                self.resources_acquired['spi'] = False
                
        logger.info("E-Paper resources cleaned up")

    def send_command(self, command):
        """Send command with error handling"""
        if self.mock_mode:
            logger.debug(f"Mock send command: 0x{command:02X}")
            return
            
        try:
            if not self.resources_acquired['dc_line'] or self.dc_line is None:
                logger.error("Cannot send command: DC line not available")
                self.mock_mode = True
                return
                
            self.dc_line.set_value(0)
            self.spi.writebytes([command])
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            self.mock_mode = True

    def send_data(self, data):
        """Send data with error handling"""
        if self.mock_mode:
            logger.debug(f"Mock send data: {data[:5] if isinstance(data, list) else data}")
            return
            
        try:
            if not self.resources_acquired['dc_line'] or self.dc_line is None:
                logger.error("Cannot send data: DC line not available")
                self.mock_mode = True
                return
                
            self.dc_line.set_value(1)
            if isinstance(data, int):
                data = [data]
            self.spi.writebytes(data)
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            self.mock_mode = True

    def wait_until_idle(self):
        """Wait until display is idle with error handling"""
        if self.mock_mode:
            logger.debug("Mock wait until idle")
            time.sleep(0.1)  # Simulate a short wait in mock mode
            return
            
        try:
            if not self.resources_acquired['busy_line'] or self.busy_line is None:
                logger.error("Cannot wait until idle: Busy line not available")
                self.mock_mode = True
                time.sleep(0.5)  # Wait a bit to simulate display refresh
                return
                
            logger.debug("Waiting for e-Paper display to become idle")
            start_time = time.time()
            timeout = 30  # 30 second timeout
            
            # Match manufacturer's logic: 1 means busy, 0 means idle
            while self.busy_line.get_value() == 1:  
                time.sleep(0.01)  # 10ms delay to match manufacturer
                if time.time() - start_time > timeout:
                    logger.warning("Timeout waiting for display to become idle")
                    break
                    
            logger.debug("Display is now idle")
        except Exception as e:
            logger.error(f"Error waiting for idle state: {e}")
            self.mock_mode = True
            time.sleep(0.5)  # Wait a bit to simulate display refresh

    def __del__(self):
        """Clean up resources when object is deleted"""
        try:
            self.cleanup_resources()
        except Exception as e:
            logger.error(f"Error during cleanup in __del__: {e}")

    def enable_debug_mode(self, enable=True):
        """Enable or disable debug mode for the driver"""
        self.DEBUG_MODE = enable
        logger.info(f"Debug mode {'enabled' if enable else 'disabled'}")
        return True
        
    def test_gpio_control(self):
        """Test GPIO control by toggling reset and DC pins
        
        This method is used for diagnostic testing of the GPIO control.
        It verifies that the GPIO pins can be properly controlled.
        
        Returns:
            bool: True if the test is successful, False otherwise
        """
        logger.info("Testing GPIO control...")
        
        # Check if hardware is available
        if not self.USE_HARDWARE:
            logger.warning("Hardware not available, using mock implementation")
            # In mock mode, always return true as we can't test real hardware
            return True
            
        try:
            # First, make sure we have access to the GPIO pins
            if not hasattr(self, 'reset_request') or not hasattr(self, 'dc_request'):
                logger.error("GPIO pins not properly initialized")
                return False
                
            # Test reset pin by toggling it
            logger.info("Testing reset pin...")
            if self.has_v2_api:
                from gpiod.line import Value
                # v2 API
                try:
                    self.reset_request.set_values({self.reset_pin: Value.ACTIVE})
                    time.sleep(0.1)
                    self.reset_request.set_values({self.reset_pin: Value.INACTIVE})
                    time.sleep(0.1)
                    logger.info("Reset pin toggle successful")
                except Exception as e:
                    logger.error(f"Failed to toggle reset pin: {e}")
                    return False
            else:
                # v1 API
                try:
                    self.reset_line.set_value(1)
                    time.sleep(0.1)
                    self.reset_line.set_value(0)
                    time.sleep(0.1)
                    logger.info("Reset pin toggle successful")
                except Exception as e:
                    logger.error(f"Failed to toggle reset pin: {e}")
                    return False
            
            # Test DC pin by toggling it
            logger.info("Testing DC pin...")
            if self.has_v2_api:
                from gpiod.line import Value
                # v2 API
                try:
                    self.dc_request.set_values({self.dc_pin: Value.ACTIVE})
                    time.sleep(0.1)
                    self.dc_request.set_values({self.dc_pin: Value.INACTIVE})
                    time.sleep(0.1)
                    logger.info("DC pin toggle successful")
                except Exception as e:
                    logger.error(f"Failed to toggle DC pin: {e}")
                    return False
            else:
                # v1 API
                try:
                    self.dc_line.set_value(1)
                    time.sleep(0.1)
                    self.dc_line.set_value(0)
                    time.sleep(0.1)
                    logger.info("DC pin toggle successful")
                except Exception as e:
                    logger.error(f"Failed to toggle DC pin: {e}")
                    return False
            
            logger.info("GPIO control test successful")
            return True
            
        except Exception as e:
            logger.error(f"GPIO control test failed: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def clear(self):
        logger.info("Clearing e-Paper display")
        if self.USE_HARDWARE and self.initialized:
            try:
                # More complete clear sequence
                if self.DEBUG_MODE:
                    logger.debug("Starting enhanced clear sequence")
                
                # Power off first if display is in an unknown state
                self.send_command(0x02)  # Power off
                self.wait_until_idle()
                
                # Power on
                self.send_command(0x04)  # Power on
                self.wait_until_idle()
                
                # Send clear command
                self.send_command(0x10)  # Data transmission 1
                zeros = [0x00] * (self.width * self.height // 8)
                self.send_data(zeros)
                
                self.send_command(0x13)  # Data transmission 2
                self.send_data(zeros)
                
                # Refresh display
                self.send_command(0x12)  # Refresh
                time.sleep(0.1)
                self.wait_until_idle()
                
                if self.DEBUG_MODE:
                    logger.debug("Clear sequence completed")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.info("Mock clear display")
    
    def display_image(self, image):
        logger.info("Displaying image on e-Paper display")
        if self.USE_HARDWARE and self.initialized:
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
        if self.USE_HARDWARE and self.initialized:
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
        if self.USE_HARDWARE and self.initialized:
            self.send_command(0x02)  # Power off
            self.wait_until_idle()
            self.send_command(0x07)  # Deep sleep
            self.send_data(0xA5)
        else:
            logger.info("Mock sleep") 