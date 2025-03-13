#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
Wrapper for Waveshare E-Ink Display Driver

This wrapper uses the manufacturer's driver directly instead of reimplementing it.
It adds convenience functions and error handling on top of the original API.
"""

import os
import sys
import time
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)

class WaveshareWrapper:
    """
    Wrapper for Waveshare E-Ink display drivers
    
    This class wraps the manufacturer's driver to ensure exact compatibility
    with their implementation while adding our own conveniences.
    """
    
    # Gray levels as defined by the manufacturer
    GRAY1 = 0x00  # Black
    GRAY2 = 0x01  # Dark Gray
    GRAY3 = 0x02  # Light Gray
    GRAY4 = 0x03  # White (Same as 0xFF)
    
    def __init__(self, mock_mode=None, handle_errors=None, busy_timeout=None):
        """Initialize the wrapper"""
        self.mock_mode = mock_mode if mock_mode is not None else os.environ.get('EINK_MOCK_MODE', '0') == '1'
        self.nvme_compatible = os.environ.get('NVME_COMPATIBLE', '0') == '1'
        self.handle_errors = handle_errors if handle_errors is not None else os.environ.get('EINK_HANDLE_ERRORS', '1') == '1'
        self.busy_timeout = busy_timeout if busy_timeout is not None else int(os.environ.get('EINK_BUSY_TIMEOUT', 10))
        self.epd = None
        self.initialized = False
        
        # Try to import the manufacturer's module
        self._import_manufacturer_module()
    
    def _import_manufacturer_module(self):
        """Import the manufacturer's module"""
        try:
            # If we're in mock mode, don't even try to import
            if self.mock_mode:
                print("Running in mock mode - not importing hardware driver")
                return
                
            # Import the manufacturer's module
            from waveshare_epd import epd3in7
            self.epd = epd3in7.EPD()
            
            # Store display dimensions
            self.width = self.epd.width
            self.height = self.epd.height
            
            print(f"Successfully imported manufacturer's driver")
            print(f"Display dimensions: {self.width}x{self.height}")
            
        except ImportError as e:
            error_msg = f"Could not import manufacturer's driver: {e}"
            print(error_msg)
            if self.handle_errors:
                print("Falling back to mock mode")
                self.mock_mode = True
            else:
                raise ImportError(error_msg)
    
    def init(self, mode=0):
        """
        Initialize the display
        Args:
            mode: 0 = 4Gray mode, 1 = 1Gray mode
        """
        if self.initialized:
            return
            
        try:
            if self.mock_mode:
                print(f"Mock init with mode={mode}")
                self.width = 280
                self.height = 480
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
                self.width = 280
                self.height = 480
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
    
    def display_text(self, text, x=10, y=10, font_size=24):
        """
        Display text on the screen
        Args:
            text: Text to display
            x: X position
            y: Y position
            font_size: Font size
        """
        if not self.initialized:
            self.init(0)  # 4-Gray mode
            
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a blank image with white background
            image = Image.new('L', (self.width, self.height), 255)
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
                        break
                    except Exception:
                        pass
            
            if font is None:
                print("No TrueType fonts found, using default")
                font = ImageFont.load_default()
            
            # Draw text
            draw.text((x, y), text, font=font, fill=0)
            
            # Display the image
            self.display(image)
            
        except Exception as e:
            error_msg = f"Error displaying text: {e}"
            print(error_msg)
            traceback.print_exc()
            
            if not self.handle_errors:
                raise RuntimeError(error_msg)

# For backward compatibility, make WaveshareEPD3in7 an alias of WaveshareWrapper
WaveshareEPD3in7 = WaveshareWrapper 