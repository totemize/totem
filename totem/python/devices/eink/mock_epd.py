#!/usr/bin/env python3
"""
Mock driver for e-ink display
This provides a non-hardware implementation for testing and fallback
"""

import time
import logging

# Display resolution (matching the real display)
EPD_WIDTH = 280
EPD_HEIGHT = 480

class MockEPD:
    """Mock e-Paper driver implementation"""
    
    def __init__(self):
        """Initialize the mock driver"""
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.initialized = False
        print("Mock EPD: Initializing mock e-ink display driver")
    
    def init(self):
        """Initialize the mock display"""
        print("Mock EPD: Initializing display")
        time.sleep(0.5)  # Simulate initialization delay
        self.initialized = True
    
    def Clear(self):
        """Clear the mock display"""
        if not self.initialized:
            self.init()
        print("Mock EPD: Clearing display")
        time.sleep(0.2)  # Simulate clearing delay
    
    def display(self, image):
        """Display an image on the mock display"""
        if not self.initialized:
            self.init()
        if image is None:
            print("Mock EPD: No image to display")
            return
        
        print(f"Mock EPD: Displaying image of size {image.width}x{image.height}")
        time.sleep(0.5)  # Simulate display delay
    
    def display_text(self, text, x=10, y=10, font_size=24):
        """Display text on the mock display"""
        if not self.initialized:
            self.init()
        print(f"Mock EPD: Displaying text '{text}' at ({x},{y}) with font size {font_size}")
        time.sleep(0.3)  # Simulate text display delay
    
    def sleep(self):
        """Put the mock display to sleep"""
        if not self.initialized:
            return
        print("Mock EPD: Putting display to sleep")
        time.sleep(0.1)  # Simulate sleep delay
    
    def close(self):
        """Close the mock display"""
        print("Mock EPD: Closing display")
        self.initialized = False 