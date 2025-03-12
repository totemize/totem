#!/usr/bin/env python3
"""
Waveshare 2.13inch e-Paper HAT driver for Raspberry Pi 5 with software CS control.
Resolution: 250x122 pixels
Interface: SPI
Color: Black and White
"""

import os
import time
import traceback
import logging
try:
    import gpiod
    import spidev
    import numpy as np
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False

from utils.logger import logger
from devices.eink.eink import EInkDeviceInterface

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
    """Driver for Waveshare 2.13inch e-Paper HAT (Pi 5 compatible) with Software CS"""
    
    # Display constants
    width = 250
    height = 122
    
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
        self.initialized = False
        self.USE_HARDWARE = False  # Initialize as False by default
        self.DEBUG_MODE = False    # Debug mode for SPI/GPIO commands
        
        # GPIO pin definitions
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8  # We'll use software CS control instead of hardware
        
        # Use alternative pins if specified by environment variable
        if os.environ.get('USE_ALT_EINK_PINS'):
            logger.info("Using alternative E-Ink pins specified by environment variable")
            self.reset_pin = int(os.environ.get('EINK_RST_PIN', 27))
            self.dc_pin = int(os.environ.get('EINK_DC_PIN', 22))
            self.busy_pin = int(os.environ.get('EINK_BUSY_PIN', 23))
            self.cs_pin = int(os.environ.get('EINK_CS_PIN', 7))
        
        # Use alternative SPI device if specified by environment variable
        self.spi_bus = int(os.environ.get('EINK_SPI_BUS', 0))
        self.spi_device = int(os.environ.get('EINK_SPI_DEVICE', 0))
        
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
            # Check if SPI device exists
            spi_device_path = f'/dev/spidev{self.spi_bus}.{self.spi_device}'
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
            logger.info("Using Pi 5 compatible GPIO (gpiod) and SPI with software CS")
            
            # Initialize SPI
            logger.info(f"Opening SPI device bus {self.spi_bus}, device {self.spi_device}")
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = 1000000  # 1MHz (reduced from 2MHz for stability)
            self.spi.mode = 0
            
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
        logger.info("Initializing Waveshare 2.13in e-Paper HAT (Pi 5 compatible with software CS).")
        
        if self.USE_HARDWARE:
            try:
                # Clean up any previous resources
                self._cleanup_gpio()
                
                # Configure GPIO lines using appropriate API
                if self.has_v2_api:
                    self._init_gpio_v2()
                else:
                    self._init_gpio_v1()
                    
                # Initialize the display
                self._init_display()
            except Exception as e:
                logger.error(f"Error initializing Pi 5 GPIO: {e}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                self.initialized = False
                self.USE_HARDWARE = False
                self._cleanup_gpio()
        else:
            # Mock initialization
            logger.info("Mock initialization complete")
            self.initialized = True
    
    def _init_display(self):
        """Initialize the display."""
        logger.debug("Initializing display")
        
        # Reset the display
        self.reset()
        
        # Send initialization commands
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data(0x79)  # (HEIGHT-1) & 0xFF = 121 = 0x79
        self.send_data(0x00)  # ((HEIGHT-1) >> 8) & 0xFF
        self.send_data(0x00)  # GD=0, SM=0, TB=0
        
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
        
        # Set the look-up table for display refresh
        self._set_lut()
        
        self.initialized = True
        logger.debug("Display initialization complete")

    def _set_lut(self):
        """Set the look-up table for display refresh."""
        logger.debug("Setting LUT")
        
        # LUT for Waveshare 2.13 inch E-Paper (full refresh)
        lut_full_update = [
            0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11, 
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
            0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 
            0x01, 0x00, 0x00, 0x00, 0x00, 0x00
        ]
        
        self.send_command(self.WRITE_LUT_REGISTER)
        for i in range(len(lut_full_update)):
            self.send_data(lut_full_update[i])
        
        logger.debug("LUT set complete")

    def _init_gpio_v2(self):
        """Initialize GPIO using v2 API"""
        logger.info("Initializing GPIO using gpiod v2 API")
        
        from gpiod.line_settings import LineSettings
        from gpiod.line import Value, Direction
        
        # Store API-specific constants
        self.Value = Value
        
        # Open the chip
        logger.info("Opening GPIO chip")
        self.chip = gpiod.Chip('/dev/gpiochip0')
        
        # Create settings for output and input pins
        output_settings = LineSettings(direction=Direction.OUTPUT)
        input_settings = LineSettings(direction=Direction.INPUT)
        
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
        
        # Request CS pin as output (using software CS control)
        logger.info(f"Requesting CS pin {self.cs_pin} as output (software controlled)")
        try:
            self.cs_request = self.chip.request_lines(
                {self.cs_pin: output_settings}, 
                consumer="totem-cs"
            )
            # Set CS to inactive (HIGH) by default
            self.cs_request.set_values({self.cs_pin: Value.INACTIVE})
        except OSError as e:
            if "Device or resource busy" in str(e):
                logger.warning(f"CS pin {self.cs_pin} is busy. Another process may be using it.")
                logger.warning("Will try to continue without CS pin control")
            else:
                raise
        
        # Check if sufficient required requests were successful
        if (hasattr(self, 'reset_request') and 
            hasattr(self, 'dc_request') and 
            hasattr(self, 'busy_request')):
            # Reset the display
            self.reset()
            logger.info("Pi 5 e-Paper initialization with software CS complete")
        else:
            logger.warning("Some required GPIO pins could not be requested. Falling back to mock mode.")
            self.initialized = False
            self.USE_HARDWARE = False

    def _init_gpio_v1(self):
        """Initialize GPIO using v1 API"""
        logger.info("Initializing GPIO using gpiod v1 API")
        
        # Open the chip
        logger.info("Opening GPIO chip")
        self.chip = gpiod.Chip('/dev/gpiochip0')
        
        # Request each line individually
        logger.info(f"Requesting reset pin {self.reset_pin} as output")
        try:
            self.reset_line = self.chip.get_line(self.reset_pin)
            self.reset_line.request(consumer="totem-reset", type=gpiod.LINE_REQ_DIR_OUT)
        except Exception as e:
            if "busy" in str(e).lower():
                logger.warning(f"Reset pin {self.reset_pin} is busy. Another process may be using it.")
            else:
                logger.error(f"Error requesting reset pin: {e}")
            self.reset_line = None
        
        logger.info(f"Requesting dc pin {self.dc_pin} as output")
        try:
            self.dc_line = self.chip.get_line(self.dc_pin)
            self.dc_line.request(consumer="totem-dc", type=gpiod.LINE_REQ_DIR_OUT)
        except Exception as e:
            if "busy" in str(e).lower():
                logger.warning(f"DC pin {self.dc_pin} is busy. Another process may be using it.")
            else:
                logger.error(f"Error requesting DC pin: {e}")
            self.dc_line = None
        
        logger.info(f"Requesting busy pin {self.busy_pin} as input")
        try:
            self.busy_line = self.chip.get_line(self.busy_pin)
            self.busy_line.request(consumer="totem-busy", type=gpiod.LINE_REQ_DIR_IN)
        except Exception as e:
            if "busy" in str(e).lower():
                logger.warning(f"Busy pin {self.busy_pin} is busy. Another process may be using it.")
            else:
                logger.error(f"Error requesting busy pin: {e}")
            self.busy_line = None
        
        # Request CS pin as output (using software CS control)
        logger.info(f"Requesting CS pin {self.cs_pin} as output (software controlled)")
        try:
            self.cs_line = self.chip.get_line(self.cs_pin)
            self.cs_line.request(consumer="totem-cs", type=gpiod.LINE_REQ_DIR_OUT)
            # Set CS to inactive (HIGH) by default
            self.cs_line.set_value(1)
        except Exception as e:
            if "busy" in str(e).lower():
                logger.warning(f"CS pin {self.cs_pin} is busy. Another process may be using it.")
                logger.warning("Will try to continue without CS pin control")
            else:
                logger.error(f"Error requesting CS pin: {e}")
            self.cs_line = None
        
        # Check if sufficient required lines were successfully requested
        if self.reset_line and self.dc_line and self.busy_line:
            # Reset the display
            self.reset()
            logger.info("Pi 5 e-Paper initialization with software CS complete")
        else:
            logger.warning("Some required GPIO pins could not be requested. Falling back to mock mode.")
            self.initialized = False
            self.USE_HARDWARE = False

    def _cleanup_gpio(self):
        """Clean up GPIO resources"""
        logger.info("Cleaning up GPIO resources")
        
        # V2 API cleanup
        if hasattr(self, 'reset_request'):
            try:
                self.reset_request.release()
                logger.info("Released reset request")
            except:
                pass
        
        if hasattr(self, 'dc_request'):
            try:
                self.dc_request.release()
                logger.info("Released dc request")
            except:
                pass
                
        if hasattr(self, 'busy_request'):
            try:
                self.busy_request.release()
                logger.info("Released busy request")
            except:
                pass
        
        if hasattr(self, 'cs_request'):
            try:
                self.cs_request.release()
                logger.info("Released cs request")
            except:
                pass
        
        # V1 API cleanup
        if hasattr(self, 'reset_line') and self.reset_line:
            try:
                self.reset_line.release()
                logger.info("Released reset line")
            except:
                pass
        
        if hasattr(self, 'dc_line') and self.dc_line:
            try:
                self.dc_line.release()
                logger.info("Released dc line")
            except:
                pass
        
        if hasattr(self, 'busy_line') and self.busy_line:
            try:
                self.busy_line.release()
                logger.info("Released busy line")
            except:
                pass
        
        if hasattr(self, 'cs_line') and self.cs_line:
            try:
                self.cs_line.release()
                logger.info("Released cs line")
            except:
                pass
        
        if hasattr(self, 'chip'):
            try:
                self.chip.close()
                logger.info("Closed GPIO chip")
            except:
                pass
    
    def enable_debug_mode(self, enable=True):
        """Enable or disable detailed debug logging for hardware commands"""
        self.DEBUG_MODE = enable
        logger.info(f"Debug mode {'enabled' if enable else 'disabled'}")
        return self.DEBUG_MODE
    
    def reset(self):
        if self.USE_HARDWARE:
            try:
                logger.debug("Resetting display with enhanced sequence")
                if self.has_v2_api:
                    self._reset_v2()
                else:
                    self._reset_v1()
                
                if self.DEBUG_MODE:
                    logger.debug("Enhanced reset sequence completed")
            except Exception as e:
                logger.error(f"Error during reset: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.debug("Mock reset")
            time.sleep(0.6)
            
    def _reset_v2(self):
        """Reset sequence using v2 API"""
        from gpiod.line import Value
        
        # First ensure reset is inactive (HIGH)
        self.reset_request.set_values({self.reset_pin: Value.INACTIVE})
        time.sleep(0.2)  # Short delay
        
        # Reset sequence (LOW-HIGH-LOW-HIGH)
        self.reset_request.set_values({self.reset_pin: Value.ACTIVE})
        time.sleep(0.2)  # Longer pulse
        self.reset_request.set_values({self.reset_pin: Value.INACTIVE})
        time.sleep(0.2)  # Final stabilization
            
    def _reset_v1(self):
        """Reset sequence using v1 API"""
        # First ensure reset is inactive (HIGH)
        self.reset_line.set_value(1)
        time.sleep(0.2)  # Short delay
        
        # Reset sequence (LOW-HIGH)
        self.reset_line.set_value(0)
        time.sleep(0.2)  # Longer pulse
        self.reset_line.set_value(1)
        time.sleep(0.2)  # Final stabilization
    
    def send_command(self, command):
        if self.USE_HARDWARE:
            try:
                if self.DEBUG_MODE:
                    logger.debug(f"Sending command: 0x{command:02X}")
                
                # Set DC LOW for command
                if self.has_v2_api:
                    from gpiod.line import Value
                    self.dc_request.set_values({self.dc_pin: Value.INACTIVE})
                    
                    # Activate CS (LOW)
                    if hasattr(self, 'cs_request'):
                        self.cs_request.set_values({self.cs_pin: Value.ACTIVE})
                else:
                    self.dc_line.set_value(0)
                    
                    # Activate CS (LOW)
                    if hasattr(self, 'cs_line') and self.cs_line:
                        self.cs_line.set_value(0)
                
                # Send the command
                self.spi.xfer2([command])
                
                # Deactivate CS (HIGH)
                if self.has_v2_api:
                    if hasattr(self, 'cs_request'):
                        self.cs_request.set_values({self.cs_pin: Value.INACTIVE})
                else:
                    if hasattr(self, 'cs_line') and self.cs_line:
                        self.cs_line.set_value(1)
                
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                if self.DEBUG_MODE:
                    logger.error(traceback.format_exc())
        else:
            if self.DEBUG_MODE:
                logger.debug(f"Mock send command: 0x{command:02X}")
    
    def send_data(self, data):
        if self.USE_HARDWARE:
            try:
                if self.DEBUG_MODE:
                    if isinstance(data, list) and len(data) > 10:
                        logger.debug(f"Sending data: [{data[0]:02X}, {data[1]:02X}, ... {len(data)} bytes]")
                    elif isinstance(data, list):
                        logger.debug(f"Sending data: {[f'0x{d:02X}' for d in data]}")
                    else:
                        logger.debug(f"Sending data: 0x{data:02X}")
                
                # Set DC HIGH for data
                if self.has_v2_api:
                    from gpiod.line import Value
                    self.dc_request.set_values({self.dc_pin: Value.ACTIVE})
                    
                    # Activate CS (LOW)
                    if hasattr(self, 'cs_request'):
                        self.cs_request.set_values({self.cs_pin: Value.ACTIVE})
                else:
                    self.dc_line.set_value(1)
                    
                    # Activate CS (LOW)
                    if hasattr(self, 'cs_line') and self.cs_line:
                        self.cs_line.set_value(0)
                
                # Send the data
                if isinstance(data, int):
                    self.spi.xfer2([data])
                else:
                    # Write data in chunks to avoid buffer issues
                    chunk_size = 512  # Reduced from 1024 for reliability
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        self.spi.xfer2(chunk)
                        # Add a small delay between chunks for reliability
                        time.sleep(0.001)
                
                # Deactivate CS (HIGH)
                if self.has_v2_api:
                    if hasattr(self, 'cs_request'):
                        self.cs_request.set_values({self.cs_pin: Value.INACTIVE})
                else:
                    if hasattr(self, 'cs_line') and self.cs_line:
                        self.cs_line.set_value(1)
                
            except Exception as e:
                logger.error(f"Error sending data: {e}")
                if self.DEBUG_MODE:
                    logger.error(traceback.format_exc())
        else:
            if self.DEBUG_MODE:
                if isinstance(data, list) and len(data) > 10:
                    logger.debug(f"Mock send data: [{data[0]:02X}, {data[1]:02X}, ... {len(data)} bytes]")
                elif isinstance(data, list):
                    logger.debug(f"Mock send data: {[f'0x{d:02X}' for d in data]}")
                else:
                    logger.debug(f"Mock send data: 0x{data:02X}")
    
    def wait_until_idle(self):
        """Wait until the display is idle (BUSY pin high)."""
        logger.debug("Waiting for display to be idle")
        
        if not self.USE_HARDWARE:
            logger.debug("Mock mode: simulating wait")
            time.sleep(1)
            return
        
        try:
            start_time = time.time()
            timeout = 20  # 20 seconds timeout (increased from 10)
            
            while True:
                # Check if BUSY pin is HIGH (idle)
                if self.has_v2_api:
                    values = self.busy_request.get_values()
                    busy_value = values[self.busy_pin] if self.busy_pin in values else 0
                    if busy_value == 1:
                        break
                else:
                    if self.busy_line.get_value() == 1:
                        break
                
                # Check for timeout
                if time.time() - start_time > timeout:
                    logger.warning("Timeout waiting for display to be idle")
                    break
                
                # Short delay to prevent CPU hogging
                time.sleep(0.1)
            
            logger.debug("Display is idle")
        except Exception as e:
            logger.error(f"Error waiting for idle: {e}")
            # Fall back to a fixed delay if there's an error
            logger.warning("Using fixed delay instead")
            time.sleep(2)
    
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

    def _update(self):
        """Update the display with the current buffer."""
        logger.debug("Updating display")
        
        # Trigger display update
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC4)  # Enable clock and analog, disable oscillator
        self.send_command(self.MASTER_ACTIVATION)
        self.send_command(self.TERMINATE_FRAME_READ_WRITE)
        
        # Wait for the display to finish updating
        self.wait_until_idle()
        
        logger.debug("Display update complete")
            
    def clear(self):
        logger.info("Clearing e-Paper display")
        if not self.initialized:
            self.init()
            
        if self.USE_HARDWARE:
            try:
                # Set window and cursor
                self._set_window(0, 0, self.width-1, self.height-1)
                self._set_cursor(0, 0)
                
                # Send write RAM command
                self.send_command(self.WRITE_RAM)
                
                # Send all white pixels
                zeros = [0xFF] * (self.width * self.height // 8)  # 0xFF = white
                self.send_data(zeros)
                
                # Update display
                self._update()
                
                if self.DEBUG_MODE:
                    logger.debug("Clear sequence completed")
            except Exception as e:
                logger.error(f"Error clearing display: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.info("Mock clear display")
    
    def display_image(self, image):
        logger.info("Displaying image on e-Paper display")
        if not self.initialized:
            self.init()
            
        if self.USE_HARDWARE:
            try:
                # Process image
                if image.mode != '1':
                    logger.debug(f"Converting image from {image.mode} to 1-bit mode")
                    image = image.convert('1')
                
                if image.size[0] != self.width or image.size[1] != self.height:
                    logger.debug(f"Resizing image from {image.size} to {self.width}x{self.height}")
                    image = image.resize((self.width, self.height))
        
                # Get image data
                logger.debug("Converting image to buffer data")
                pixels = np.array(image)
                buffer = np.packbits(~pixels.astype(bool)).tolist()  # Invert: 0 = black, 1 = white
                
                # Set window and cursor
                logger.debug("Setting window and cursor position")
                self._set_window(0, 0, self.width-1, self.height-1)
                self._set_cursor(0, 0)
                
                # Send data
                logger.debug(f"Sending data to RAM (buffer size: {len(buffer)} bytes)")
                self.send_command(self.WRITE_RAM)
                self.send_data(buffer)
                
                # Update display
                logger.debug("Triggering display update")
                self._update()
                
                logger.info("Image displayed successfully")
            except Exception as e:
                logger.error(f"Error displaying image: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.info(f"Mock display image with size {image.size}")
    
    def display_bytes(self, image_bytes):
        logger.info("Displaying raw bytes on e-Paper display")
        if not self.initialized:
            self.init()
            
        if self.USE_HARDWARE:
            # Check data size
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
        else:
            logger.info("Mock display bytes")
    
    def sleep(self):
        logger.info("Putting e-Paper to sleep")
        if self.USE_HARDWARE and self.initialized:
            self.send_command(self.DEEP_SLEEP_MODE)
            self.send_data(0x01)  # Enter deep sleep
        else:
            logger.info("Mock sleep")
    
    def __del__(self):
        try:
            self._cleanup_gpio()
            
            if hasattr(self, 'spi') and not isinstance(self.spi, MockSpiDev) and hasattr(self.spi, 'close'):
                self.spi.close()
            
            logger.info("E-Paper resources cleaned up")
        except Exception as e:
            logger.error(f"Error in __del__: {e}") 