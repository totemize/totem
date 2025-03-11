#!/usr/bin/env python3
"""
Waveshare 3.7inch e-Paper HAT driver for Raspberry Pi 5.
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
from devices.eink.eink_device_interface import EInkDeviceInterface, MockSpiDev, MockGPIO, MockValue, MockDirection

class Driver(EInkDeviceInterface):
    # Class variables
    width = 480
    height = 280
    
    def __init__(self):
        self.initialized = False
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
                # Clean up any previous resources
                self._cleanup_gpio()
                
                # Configure GPIO lines using appropriate API
                if self.has_v2_api:
                    self._init_gpio_v2()
                else:
                    self._init_gpio_v1()
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
    
    def _init_gpio_v2(self):
        """Initialize GPIO using v2 API"""
        logger.info("Initializing GPIO using gpiod v2 API")
        
        from gpiod.line_settings import LineSettings
        from gpiod.line import Value, Direction
        
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
        
        # Note: We're not requesting the CS pin as it's controlled by the SPI hardware
        logger.info(f"Using hardware CS on pin {self.cs_pin} (managed by SPI driver)")
        
        # Check if all required lines were successfully requested
        if self.reset_line and self.dc_line and self.busy_line:
            # Reset the display
            self.reset()
            self.initialized = True
            logger.info("Pi 5 e-Paper initialization complete")
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
                
                # Send power on command after reset
                self.send_command(0x04)  # Power on
                self.wait_until_idle()
                
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
        time.sleep(0.05)  # Short delay
        
        # Reset sequence (LOW-HIGH-LOW-HIGH)
        self.reset_request.set_values({self.reset_pin: Value.ACTIVE})
        time.sleep(0.2)  # Longer pulse
        self.reset_request.set_values({self.reset_pin: Value.INACTIVE})
        time.sleep(0.02)  # Short delay
        self.reset_request.set_values({self.reset_pin: Value.ACTIVE})
        time.sleep(0.2)  # Longer pulse
        self.reset_request.set_values({self.reset_pin: Value.INACTIVE})
        time.sleep(0.2)  # Final stabilization
            
    def _reset_v1(self):
        """Reset sequence using v1 API"""
        # First ensure reset is inactive (HIGH)
        self.reset_line.set_value(1)
        time.sleep(0.05)  # Short delay
        
        # Reset sequence (LOW-HIGH-LOW-HIGH)
        self.reset_line.set_value(0)
        time.sleep(0.2)  # Longer pulse
        self.reset_line.set_value(1)
        time.sleep(0.02)  # Short delay
        self.reset_line.set_value(0)
        time.sleep(0.2)  # Longer pulse
        self.reset_line.set_value(1)
        time.sleep(0.2)  # Final stabilization
    
    def send_command(self, command):
        if self.USE_HARDWARE:
            try:
                if self.DEBUG_MODE:
                    logger.debug(f"Sending command: 0x{command:02X}")
                
                if self.has_v2_api:
                    from gpiod.line import Value
                    self.dc_request.set_values({self.dc_pin: Value.INACTIVE})  # DC LOW for command
                else:
                    self.dc_line.set_value(0)  # DC LOW for command
                
                self.spi.writebytes([command])
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
                
                if self.has_v2_api:
                    from gpiod.line import Value
                    self.dc_request.set_values({self.dc_pin: Value.ACTIVE})  # DC HIGH for data
                else:
                    self.dc_line.set_value(1)  # DC HIGH for data
                
                if isinstance(data, int):
                    self.spi.writebytes([data])
                else:
                    # Write data in chunks to avoid buffer issues
                    chunk_size = 1024
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        self.spi.writebytes(chunk)
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
        if self.USE_HARDWARE:
            try:
                if self.DEBUG_MODE:
                    logger.debug("Waiting for display to be idle")
                
                # Different waiting logic for v1/v2 API
                if self.has_v2_api:
                    from gpiod.line import Value
                    while True:
                        values = self.busy_request.get_values()
                        busy_value = values[self.busy_pin]
                        if busy_value == Value.INACTIVE:  # HIGH is idle
                            break
                        time.sleep(0.01)
                else:
                    while self.busy_line.get_value() == 0:  # LOW is busy
                        time.sleep(0.01)
                        
                if self.DEBUG_MODE:
                    logger.debug("Display is now idle")
            except Exception as e:
                logger.error(f"Error waiting for idle: {e}")
                if self.DEBUG_MODE:
                    logger.error(traceback.format_exc())
                time.sleep(1)  # Safe default wait time
        else:
            if self.DEBUG_MODE:
                logger.debug("Mock wait until idle")
            time.sleep(0.1)
            
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
    
    def __del__(self):
        try:
            self._cleanup_gpio()
            
            if hasattr(self, 'spi') and not isinstance(self.spi, MockSpiDev) and hasattr(self.spi, 'close'):
                self.spi.close()
            
            logger.info("E-Paper resources cleaned up")
        except Exception as e:
            logger.error(f"Error in __del__: {e}") 