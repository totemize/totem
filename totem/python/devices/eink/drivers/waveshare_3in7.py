#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Driver for Waveshare 3.7inch E-Ink Display

This driver uses the manufacturer's driver directly instead of reimplementing it.
It adds our specific functionality (error handling, NVME compatibility, etc.) on top
of the manufacturer's implementation for perfect compatibility.
"""

import os
import sys
import time
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)

# Pin definitions (for environment variables and documentation)
RST_PIN = int(os.environ.get('EINK_RST_PIN', 17)) if os.environ.get('USE_ALT_EINK_PINS') else 17
DC_PIN = int(os.environ.get('EINK_DC_PIN', 25)) if os.environ.get('USE_ALT_EINK_PINS') else 25
CS_PIN = int(os.environ.get('EINK_CS_PIN', 9)) if os.environ.get('USE_ALT_EINK_PINS') else 8
BUSY_PIN = int(os.environ.get('EINK_BUSY_PIN', 24)) if os.environ.get('USE_ALT_EINK_PINS') else 24

# Software SPI pins (only used if USE_SW_SPI=1)
MOSI_PIN = int(os.environ.get('EINK_MOSI_PIN', 10))  # GPIO 10 = MOSI
SCK_PIN = int(os.environ.get('EINK_SCK_PIN', 11))    # GPIO 11 = SCK

# Flag to use software SPI
USE_SW_SPI = os.environ.get('USE_SW_SPI', '0') == '1' or os.environ.get('NVME_COMPATIBLE', '0') == '1'

# Flag for NVME compatibility (uses alternative pins and software SPI)
NVME_COMPATIBLE = os.environ.get('NVME_COMPATIBLE', '0') == '1'

# If NVME_COMPATIBLE is set, override pins to avoid SPI conflicts
if NVME_COMPATIBLE:
    # Use pins that don't conflict with SPI0 or SPI1
    RST_PIN = int(os.environ.get('EINK_RST_PIN', 17))
    DC_PIN = int(os.environ.get('EINK_DC_PIN', 25))
    CS_PIN = int(os.environ.get('EINK_CS_PIN', 9))
    BUSY_PIN = int(os.environ.get('EINK_BUSY_PIN', 24))
    MOSI_PIN = int(os.environ.get('EINK_MOSI_PIN', 10))
    SCK_PIN = int(os.environ.get('EINK_SCK_PIN', 11))
    USE_SW_SPI = True

# Import EInkDeviceInterface at the top of the file
try:
    from devices.eink.eink import EInkDeviceInterface
except ImportError:
    try:
        from python.devices.eink.eink import EInkDeviceInterface
    except ImportError:
        # Create a placeholder class if we can't import the real one
        class EInkDeviceInterface:
            def init(self): pass
            def clear(self): pass
            def display_image(self, image): pass
            def display_bytes(self, image_bytes): pass

class WaveshareEPD3in7:
    """
    Driver for Waveshare 3.7inch e-Paper HAT
    
    This driver uses the manufacturer's original driver for perfect compatibility,
    while adding our own error handling and configuration options.
    """
    
    # Gray levels as defined by the manufacturer
    GRAY1 = 0x00  # Black
    GRAY2 = 0x01  # Dark Gray
    GRAY3 = 0x02  # Light Gray
    GRAY4 = 0x03  # White (Same as 0xFF)
    
    def __init__(self, mock_mode=None, handle_errors=None, busy_timeout=None):
        """Initialize the driver"""
        self.mock_mode = mock_mode if mock_mode is not None else os.environ.get('EINK_MOCK_MODE', '0') == '1'
        self.nvme_compatible = NVME_COMPATIBLE
        self.using_sw_spi = USE_SW_SPI
        self.handle_errors = handle_errors if handle_errors is not None else os.environ.get('EINK_HANDLE_ERRORS', '1') == '1'
        self.busy_timeout = busy_timeout if busy_timeout is not None else int(os.environ.get('EINK_BUSY_TIMEOUT', 10))
        self.epd = None
        self.initialized = False
        self.hardware_type = self._detect_hardware()
        
        if self.nvme_compatible:
            print("Running in NVME-compatible mode with software SPI")
            print(f"Using pins: RST={RST_PIN}, DC={DC_PIN}, CS={CS_PIN}, BUSY={BUSY_PIN}")
            print(f"Software SPI pins: MOSI={MOSI_PIN}, SCK={SCK_PIN}")
        
        # Import the manufacturer's driver
        self._import_manufacturer_driver()
    
    def _detect_hardware(self):
        """Detect the Raspberry Pi hardware version"""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi 5' in model:
                    print("Detected Raspberry Pi 5")
                    return "pi5"
                elif 'Raspberry Pi' in model:
                    print("Detected Raspberry Pi (pre-Pi 5)")
                    return "pi"
                else:
                    print(f"Unknown hardware: {model}")
                    return "unknown"
        except Exception as e:
            print(f"Could not detect hardware: {e}")
            return "unknown"
    
    def _import_manufacturer_driver(self):
        """Import the manufacturer's driver"""
        try:
            # If we're in mock mode, don't even try to import
            if self.mock_mode:
                print("Running in mock mode - not importing hardware driver")
                self.width = 280
                self.height = 480
                return
                
            # Set environment variable for pin configuration if needed
            if self.nvme_compatible or self.using_sw_spi:
                # The manufacturer's driver takes pin configuration from environment variable
                os.environ['EINK_RST_PIN'] = str(RST_PIN)
                os.environ['EINK_DC_PIN'] = str(DC_PIN)
                os.environ['EINK_CS_PIN'] = str(CS_PIN)
                os.environ['EINK_BUSY_PIN'] = str(BUSY_PIN)
                if self.using_sw_spi:
                    os.environ['USE_SW_SPI'] = '1'
                    os.environ['EINK_MOSI_PIN'] = str(MOSI_PIN)
                    os.environ['EINK_SCK_PIN'] = str(SCK_PIN)
                
            # For Pi 5, choose the right backend
            if self.hardware_type == "pi5":
                print("Using Pi pi5 compatible GPIO (gpiod)")
                os.environ['USE_GPIOD'] = '1'
                
            # Import the manufacturer's module
            try:
                # First try to import from the standard location
                try:
                    from waveshare_epd import epd3in7
                    print("Using system-installed waveshare_epd driver")
                except ImportError:
                    # If not found, try to import from our local package
                    try:
                        print("System driver not found, trying local package")
                        from devices.eink.waveshare_epd import epd3in7
                        print("Using local waveshare_epd driver")
                    except ImportError:
                        print("Local package not found, trying python module path")
                        from python.devices.eink.waveshare_epd import epd3in7
                        print("Using python module waveshare_epd driver")
                
                # Create the EPD instance
                self.epd = epd3in7.EPD()
                
                # Print the pin configuration for debugging
                print(f"Manufacturer driver using pins: RST={self.epd.reset_pin}, DC={self.epd.dc_pin}, CS={self.epd.cs_pin}, BUSY={self.epd.busy_pin}")
                
                # Store display dimensions
                self.width = self.epd.width
                self.height = self.epd.height
                
                print(f"Display dimensions: {self.width}x{self.height}")
                
            except ImportError as e:
                error_msg = f"Could not import manufacturer's driver: {e}"
                print(error_msg)
                if self.handle_errors:
                    print("Falling back to mock mode")
                    self.mock_mode = True
                    self.width = 280
                    self.height = 480
                else:
                    raise ImportError(error_msg)
                
        except Exception as e:
            error_msg = f"Error during driver initialization: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
                self.width = 280
                self.height = 480
            else:
                raise RuntimeError(error_msg)
    
    def init(self, mode=0):
        """
        Initialize the e-Paper display
        Args:
            mode: 0 = 4Gray mode, 1 = 1Gray mode
        """
        if self.initialized:
            return
            
        try:
            if self.mock_mode:
                print(f"Mock init with mode={mode}")
                self.initialized = True
                return
                
            # Call the manufacturer's init method
            self.epd.init(mode)
            self.initialized = True
            
        except Exception as e:
            error_msg = f"Error initializing display: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
                self.initialized = True
            else:
                raise RuntimeError(error_msg)
    
    def Clear(self, clear_color=0xFF, mode=0):
        """
        Clear the display
        Args:
            clear_color: Color to clear with (0xFF = white)
            mode: 0 = 4Gray mode, 1 = 1Gray mode
        """
        if not self.initialized:
            self.init(mode)
            
        try:
            if self.mock_mode:
                print(f"Mock clear display with color={clear_color}, mode={mode}")
                return
                
            # Call the manufacturer's clear method
            self.epd.Clear(clear_color, mode)
            
        except Exception as e:
            error_msg = f"Error clearing display: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def clear(self, clear_color=0xFF, mode=0):
        """Alias for Clear() method"""
        return self.Clear(clear_color, mode)
                
    def display_4Gray(self, buffer):
        """
        Display buffer in 4-gray mode
        Args:
            buffer: Display buffer to show
        """
        if not self.initialized:
            self.init(0)  # 4-Gray mode
            
        try:
            if self.mock_mode:
                print("Mock display_4Gray")
                return
                
            # Call the manufacturer's display_4Gray method
            self.epd.display_4Gray(buffer)
            
        except Exception as e:
            error_msg = f"Error displaying 4Gray: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def display_1Gray(self, buffer):
        """
        Display buffer in 1-gray mode
        Args:
            buffer: Display buffer to show
        """
        if not self.initialized:
            self.init(1)  # 1-Gray mode
            
        try:
            if self.mock_mode:
                print("Mock display_1Gray")
                return
                
            # Call the manufacturer's display_1Gray method
            self.epd.display_1Gray(buffer)
            
        except Exception as e:
            error_msg = f"Error displaying 1Gray: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def display(self, image):
        """
        Display an image 
        This is a convenience method that uses display_4Gray
        Args:
            image: PIL image to display
        """
        if not self.initialized:
            self.init(0)  # 4-Gray mode
            
        try:
            if self.mock_mode:
                print("Mock display")
                return
                
            # Use the manufacturer's method to convert and display
            buffer = self.getbuffer_4Gray(image)
            self.epd.display_4Gray(buffer)
            
        except Exception as e:
            error_msg = f"Error displaying image: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise RuntimeError(error_msg)
    
    def getbuffer(self, image):
        """
        Get buffer from image for 1-bit mode
        Args:
            image: PIL image
        """
        if self.mock_mode:
            print("Mock getbuffer")
            return bytearray(int(self.width * self.height / 8))
            
        try:
            # Use the manufacturer's method
            return self.epd.getbuffer(image)
        except Exception as e:
            error_msg = f"Error getting buffer: {e}"
            print(error_msg)
            
            if self.handle_errors:
                print("Falling back to mock buffer")
                return bytearray(int(self.width * self.height / 8))
            else:
                raise RuntimeError(error_msg)
    
    def getbuffer_4Gray(self, image):
        """
        Get 4-gray buffer from image
        Args:
            image: PIL image
        """
        if self.mock_mode:
            print("Mock getbuffer_4Gray")
            return bytearray(int(self.width * self.height * 2 / 8))
            
        try:
            # Use the manufacturer's method
            return self.epd.getbuffer_4Gray(image)
        except Exception as e:
            error_msg = f"Error getting 4Gray buffer: {e}"
            print(error_msg)
            
            if self.handle_errors:
                print("Falling back to mock 4Gray buffer")
                return bytearray(int(self.width * self.height * 2 / 8))
            else:
                raise RuntimeError(error_msg)
    
    def sleep(self):
        """Put the display to sleep"""
        if self.mock_mode:
            print("Mock sleep")
            return
            
        try:
            if self.epd:
                self.epd.sleep()
        except Exception as e:
            error_msg = f"Error putting display to sleep: {e}"
            print(error_msg)
            
            if not self.handle_errors:
                raise RuntimeError(error_msg)
    
    def close(self):
        """Clean up resources"""
        if self.mock_mode:
            print("Mock close")
            return
            
        try:
            # The manufacturer doesn't have a close method, but their epdconfig has module_exit
            if hasattr(self.epd, 'exit'):
                self.epd.exit()
            elif hasattr(self.epd, 'epd_exit') and callable(self.epd.epd_exit):
                self.epd.epd_exit()
            elif hasattr(self.epd, 'epdconfig') and hasattr(self.epd.epdconfig, 'module_exit'):
                self.epd.epdconfig.module_exit()
                
            print("Display resources freed")
        except Exception as e:
            error_msg = f"Error closing display: {e}"
            print(error_msg)
            
            if not self.handle_errors:
                raise RuntimeError(error_msg)
    
    def display_text(self, text, x=10, y=10, font_size=24, text_color="black", background_color="white"):
        """
        Display text on the screen
        Args:
            text: Text to display
            x: X position
            y: Y position
            font_size: Font size
            text_color: Color of the text (default: "black")
            background_color: Background color (default: "white")
        """
        print(f"WaveshareEPD3in7: display_text called with: '{text}', pos=({x},{y}), font={font_size}, colors=({text_color}, {background_color})")
        
        if not self.initialized:
            self.init(0)  # 4-Gray mode
            
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Convert color strings to RGB tuples for PIL
            def convert_color(color_name):
                if self.mock_mode:
                    color_map = {
                        "black": 0,
                        "white": 255,
                        "gray": 128
                    }
                    return color_map.get(color_name.lower(), 0 if color_name.lower() == "black" else 255)
                else:
                    color_map = {
                        "black": 0,
                        "white": 255,
                        "gray": 128
                    }
                    return color_map.get(color_name.lower(), 0 if color_name.lower() == "black" else 255)
            
            bg_color = convert_color(background_color)
            text_fill = convert_color(text_color)
            
            print(f"Creating image with background color: {bg_color}")
            # Create a blank image with the specified background color
            image = Image.new('L', (self.width, self.height), bg_color)
            draw = ImageDraw.Draw(image)
            
            # Try to find a suitable font
            font = None
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                '/usr/share/fonts/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                'C:\\Windows\\Fonts\\Arial.ttf'
            ]
            
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, font_size)
                        print(f"Using font: {path}")
                        break
                    except Exception:
                        pass
            
            if font is None:
                print("No TrueType fonts found, using default")
                font = ImageFont.load_default()
            
            # Draw text with the specified color
            print(f"Drawing text with color: {text_fill}")
            draw.text((x, y), text, font=font, fill=text_fill)
            
            # Display the image
            print("Sending image to display")
            self.display(image)
            print("Image sent to display successfully")
            
        except Exception as e:
            error_msg = f"Error displaying text: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if not self.handle_errors:
                raise RuntimeError(error_msg)

    def display_file(self, file_path, resize=True):
        """
        Display an image from a file path
        Args:
            file_path: Absolute path to the image file
            resize: Whether to resize the image to fit the display (default: True)
        """
        print(f"WaveshareEPD3in7: display_file called with: '{file_path}', resize={resize}")
        
        if not self.initialized:
            self.init(0)  # 4-Gray mode
            
        try:
            from PIL import Image
            
            # Check if file exists
            if not os.path.exists(file_path):
                error_msg = f"File not found: {file_path}"
                print(error_msg)
                if not self.handle_errors:
                    raise FileNotFoundError(error_msg)
                return
            
            # Open the image file
            print(f"Opening image file: {file_path}")
            image = Image.open(file_path)
            
            # Convert to grayscale if needed
            if image.mode != 'L':
                print(f"Converting image from {image.mode} to grayscale")
                image = image.convert('L')
            
            # Resize if needed
            if resize and (image.width != self.width or image.height != self.height):
                print(f"Resizing image from {image.width}x{image.height} to {self.width}x{self.height}")
                image = image.resize((self.width, self.height), Image.LANCZOS)
            
            # Display the image
            print("Sending image to display")
            self.display(image)
            print("Image sent to display successfully")
            
        except Exception as e:
            error_msg = f"Error displaying image file: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if not self.handle_errors:
                raise RuntimeError(error_msg)

class Driver(EInkDeviceInterface):
    """
    Driver implementation for Waveshare 3.7inch e-Paper HAT
    
    This class implements the EInkDeviceInterface and uses the WaveshareEPD3in7 class
    to interact with the hardware.
    """
    
    def __init__(self):
        """Initialize the driver"""
        # Import here to avoid circular imports
        
        # Create the underlying driver
        self.epd = WaveshareEPD3in7()
        
        # Store dimensions for convenience
        self.width = self.epd.width
        self.height = self.epd.height
        
        # Gray levels
        self.GRAY1 = self.epd.GRAY1
        self.GRAY2 = self.epd.GRAY2
        self.GRAY3 = self.epd.GRAY3
        self.GRAY4 = self.epd.GRAY4
        
        print(f"Initialized Waveshare 3.7inch driver with dimensions: {self.width}x{self.height}")
        print(f"Using pins: RST={RST_PIN}, DC={DC_PIN}, CS={CS_PIN}, BUSY={BUSY_PIN}")
        if USE_SW_SPI:
            print(f"Using software SPI with pins: MOSI={MOSI_PIN}, SCK={SCK_PIN}")
    
    def init(self):
        """Initialize the e-ink device."""
        print("Driver.init() called")
        # Always initialize in 4Gray mode (0) as in the manufacturer's example
        self.epd.init(0)  # Initialize in 4Gray mode
    
    def clear(self):
        """Clear the e-ink display."""
        print("Driver.clear() called")
        # Clear with white color (0xFF) in 4Gray mode (0)
        self.epd.Clear(0xFF, 0)  # Clear with white color in 4Gray mode
    
    def Clear(self, clear_color=0xFF, mode=0):
        """Alias for clear() method to maintain compatibility with WaveshareEPD3in7."""
        print(f"Driver.Clear({clear_color}, {mode}) called")
        self.epd.Clear(clear_color, mode)
    
    def display_image(self, image):
        """Display an image on the e-ink screen."""
        print("Driver.display_image() called")
        # Convert the image to the right format if needed
        buffer = self.epd.getbuffer_4Gray(image)
        # Display the image
        self.epd.display_4Gray(buffer)
    
    def display_bytes(self, image_bytes):
        """Display raw byte data on the e-ink screen."""
        print("Driver.display_bytes() called")
        from PIL import Image
        import io
        
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Display the image
        self.display_image(image)
    
    def sleep(self):
        """Put the display to sleep to save power."""
        print("Driver.sleep() called")
        self.epd.sleep()
    
    def close(self):
        """Clean up resources."""
        print("Driver.close() called")
        self.epd.close()
        
    def display_text(self, text, x=10, y=10, font_size=24, text_color="black", background_color="white"):
        """Display text on the e-ink screen."""
        print(f"Driver.display_text() called with: '{text}', pos=({x},{y}), font={font_size}, colors=({text_color}, {background_color})")
        self.epd.display_text(text, x, y, font_size, text_color, background_color)

    def display_file(self, file_path, resize=True):
        """Display an image from a file path on the e-ink screen.
        
        Args:
            file_path: Absolute path to the image file
            resize: Whether to resize the image to fit the display (default: True)
        """
        print(f"Driver.display_file() called with: '{file_path}', resize={resize}")
        self.epd.display_file(file_path, resize) 