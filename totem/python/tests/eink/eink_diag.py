#!/usr/bin/env python3
"""
E-Ink Hardware Diagnostic Script
A low-level script to diagnose E-Ink display issues with timeout protection
and explicit hardware control
"""

import os
import sys
import time
import logging
import signal
import traceback
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('eink-diag')

# Timeout handler
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

def with_timeout(func, timeout=5, *args, **kwargs):
    """Run function with timeout protection"""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    try:
        result = func(*args, **kwargs)
        signal.alarm(0)  # Disable the alarm
        return result
    except TimeoutError:
        logger.error(f"Function {func.__name__} timed out after {timeout} seconds")
        raise
    finally:
        signal.alarm(0)  # Ensure alarm is disabled

# Import required libraries
try:
    import gpiod
    from gpiod.line_settings import LineSettings
    import spidev
    logger.info("Successfully imported required libraries")
except ImportError as e:
    logger.error(f"Failed to import required libraries: {e}")
    sys.exit(1)

class EInkDiagnostics:
    """Low-level E-Ink diagnostics class"""
    
    def __init__(self):
        # GPIO pin definitions
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        
        # Initialize hardware resources
        self.chip = None
        self.reset_request = None
        self.dc_request = None
        self.busy_request = None
        self.spi = None
        
        # Constants
        self.Value = gpiod.line.Value
        self.Direction = gpiod.line.Direction
        
    def cleanup(self):
        """Release all hardware resources"""
        logger.info("Cleaning up hardware resources")
        
        if self.reset_request:
            try:
                self.reset_request.release()
                logger.info("Released reset pin")
            except Exception as e:
                logger.error(f"Error releasing reset pin: {e}")
                
        if self.dc_request:
            try:
                self.dc_request.release()
                logger.info("Released DC pin")
            except Exception as e:
                logger.error(f"Error releasing DC pin: {e}")
                
        if self.busy_request:
            try:
                self.busy_request.release()
                logger.info("Released busy pin")
            except Exception as e:
                logger.error(f"Error releasing busy pin: {e}")
        
        if self.spi:
            try:
                self.spi.close()
                logger.info("Closed SPI device")
            except Exception as e:
                logger.error(f"Error closing SPI device: {e}")
                
        if self.chip:
            try:
                self.chip.close()
                logger.info("Closed GPIO chip")
            except Exception as e:
                logger.error(f"Error closing GPIO chip: {e}")
    
    def check_existing_processes(self):
        """Check for processes using GPIO pins"""
        logger.info("Checking for processes using GPIO pins")
        try:
            import subprocess
            import os
            # Use specific command to check gpiochip usage without relying on lsof
            cmd = "ps aux | grep gpiod"
            output = subprocess.check_output(cmd, shell=True, text=True)
            logger.info(f"Processes using GPIO: {output}")
            
            # Kill any existing Python processes that might have GPIO access
            # but protect the current process and SSH session
            logger.info("Killing any Python processes that might be using GPIO")
            try:
                current_pid = os.getpid()
                subprocess.run(f"ps aux | grep python | grep -v {current_pid} | grep -v sshd | grep -E 'eink|gpio' | awk '{{print $2}}' | xargs kill -9 2>/dev/null || true", shell=True)
                time.sleep(1)  # Give processes time to terminate
            except:
                pass
        except Exception as e:
            logger.error(f"Error checking processes: {e}")
    
    def setup_hardware(self):
        """Set up GPIO and SPI hardware with timeout protection"""
        
        # First check for existing processes
        self.check_existing_processes()
        
        # 1. Set up GPIO
        logger.info("Setting up GPIO")
        try:
            with_timeout(self._setup_gpio, 5)
            logger.info("GPIO setup complete")
        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")
            logger.error(traceback.format_exc())
            return False
        
        # 2. Set up SPI
        logger.info("Setting up SPI")
        try:
            with_timeout(self._setup_spi, 5)
            logger.info("SPI setup complete")
        except Exception as e:
            logger.error(f"SPI setup failed: {e}")
            logger.error(traceback.format_exc())
            return False
            
        return True
    
    def _setup_gpio(self):
        """Set up GPIO with explicit handling"""
        # Open GPIO chip
        logger.info("Opening GPIO chip")
        self.chip = gpiod.Chip('/dev/gpiochip0')
        
        # Configure settings
        output_settings = LineSettings(direction=self.Direction.OUTPUT)
        input_settings = LineSettings(direction=self.Direction.INPUT)
        
        # Request each line with error handling
        try:
            logger.info(f"Requesting reset pin {self.reset_pin}")
            self.reset_request = self.chip.request_lines(
                {self.reset_pin: output_settings}, 
                consumer="eink-diag-reset"
            )
        except Exception as e:
            logger.error(f"Failed to request reset pin: {e}")
            raise
            
        try:
            logger.info(f"Requesting DC pin {self.dc_pin}")
            self.dc_request = self.chip.request_lines(
                {self.dc_pin: output_settings}, 
                consumer="eink-diag-dc"
            )
        except Exception as e:
            logger.error(f"Failed to request DC pin: {e}")
            raise
            
        try:
            logger.info(f"Requesting busy pin {self.busy_pin}")
            self.busy_request = self.chip.request_lines(
                {self.busy_pin: input_settings}, 
                consumer="eink-diag-busy"
            )
        except Exception as e:
            logger.error(f"Failed to request busy pin: {e}")
            raise
            
    def _setup_spi(self):
        """Set up SPI communication"""
        logger.info("Opening SPI device")
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 2000000  # 2MHz
        self.spi.mode = 0
        logger.info(f"SPI configured with max_speed_hz={self.spi.max_speed_hz}, mode={self.spi.mode}")
        
    def reset_display(self):
        """Perform hardware reset sequence"""
        if not self.reset_request:
            logger.error("Reset pin not initialized")
            return False
            
        logger.info("Performing hardware reset sequence")
        try:
            # Initial state (HIGH)
            self.reset_request.set_values({self.reset_pin: self.Value.INACTIVE})
            time.sleep(0.1)
            
            # Reset pulse (LOW-HIGH-LOW-HIGH)
            self.reset_request.set_values({self.reset_pin: self.Value.ACTIVE})
            time.sleep(0.2)
            self.reset_request.set_values({self.reset_pin: self.Value.INACTIVE})
            time.sleep(0.02)
            self.reset_request.set_values({self.reset_pin: self.Value.ACTIVE})
            time.sleep(0.2)
            self.reset_request.set_values({self.reset_pin: self.Value.INACTIVE})
            time.sleep(0.2)
            
            logger.info("Reset sequence completed")
            return True
        except Exception as e:
            logger.error(f"Reset sequence failed: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def send_command(self, command):
        """Send command to display"""
        if not self.dc_request or not self.spi:
            logger.error("DC pin or SPI not initialized")
            return False
            
        try:
            # Command mode (DC pin LOW)
            self.dc_request.set_values({self.dc_pin: self.Value.INACTIVE})
            self.spi.writebytes([command])
            logger.info(f"Sent command: 0x{command:02X}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def send_data(self, data):
        """Send data to display"""
        if not self.dc_request or not self.spi:
            logger.error("DC pin or SPI not initialized")
            return False
            
        try:
            # Data mode (DC pin HIGH)
            self.dc_request.set_values({self.dc_pin: self.Value.ACTIVE})
            
            if isinstance(data, int):
                self.spi.writebytes([data])
                logger.info(f"Sent data byte: 0x{data:02X}")
            else:
                # Send in chunks to avoid buffer issues
                chunk_size = 1024
                total_sent = 0
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i + chunk_size]
                    self.spi.writebytes(chunk)
                    total_sent += len(chunk)
                    if i == 0:
                        logger.info(f"Sent first chunk of data ({len(chunk)} bytes)")
                logger.info(f"Sent total of {total_sent} bytes")
                
            return True
        except Exception as e:
            logger.error(f"Failed to send data: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def wait_busy(self, timeout=10):
        """Wait for busy pin to indicate not busy (HIGH)"""
        if not self.busy_request:
            logger.error("Busy pin not initialized")
            return False
            
        logger.info("Waiting for display to be not busy")
        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                # Get busy pin value
                busy_values = self.busy_request.get_values()
                if busy_values:
                    busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(self.busy_pin)
                    logger.debug(f"Busy pin value: {busy_value}")
                    
                    # Check if not busy (INACTIVE/LOW)
                    if busy_value == self.Value.INACTIVE:
                        logger.info(f"Display ready after {time.time() - start_time:.2f} seconds")
                        return True
                        
                time.sleep(0.1)
                
            logger.error(f"Busy wait timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error waiting for busy: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def initialize_display(self):
        """Run basic display initialization sequence"""
        logger.info("Initializing display")
        
        # First reset the display
        if not self.reset_display():
            return False
            
        # Basic initialization sequence for Waveshare 3.7in display
        try:
            # Power on
            logger.info("Sending power on command")
            self.send_command(0x04)  # POWER_ON
            time.sleep(0.1)
            
            # Wait for display to be ready
            self.wait_busy(timeout=5)
            
            # Panel setting
            logger.info("Sending panel setting command")
            self.send_command(0x00)  # PANEL_SETTING
            self.send_data(0x0F)  # LUT from OTP
            
            # Set resolution
            logger.info("Setting display resolution")
            self.send_command(0x61)  # RESOLUTION_SETTING
            self.send_data(0x01)  # 480
            self.send_data(0xE0)
            self.send_data(0x01)  # 280
            self.send_data(0x18)
            
            # Set refresh control
            logger.info("Setting PLL control")
            self.send_command(0x30)  # PLL_CONTROL
            self.send_data(0x3A)  # 3A=50Hz, 29=40Hz
            
            logger.info("Display initialization complete")
            return True
        except Exception as e:
            logger.error(f"Display initialization failed: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def clear_display(self):
        """Clear the display by filling with white"""
        logger.info("Clearing display")
        
        try:
            # Calculate buffer size based on display dimensions (480x280)
            width, height = 480, 280
            buffer_size = width * height // 8
            
            # Create white buffer (0xFF = white)
            white_buffer = [0xFF] * buffer_size
            
            # Data Entry Mode
            self.send_command(0x11)  # DATA_ENTRY_MODE
            self.send_data(0x03)     # X/Y increment
            
            # Send data to clear screen
            self.send_command(0x10)  # DATA_START_TRANSMISSION_1
            self.send_data(white_buffer)
            
            self.send_command(0x13)  # DATA_START_TRANSMISSION_2
            self.send_data(white_buffer)
            
            # Refresh the display
            self.send_command(0x12)  # DISPLAY_REFRESH
            time.sleep(0.1)
            self.wait_busy(timeout=15)  # May take longer to refresh
            
            logger.info("Display cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear display: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def display_test_pattern(self):
        """Display simple test pattern"""
        logger.info("Displaying test pattern")
        
        try:
            # Create image with test pattern
            width, height = 480, 280
            image = Image.new('1', (width, height), 255)  # 255: white
            draw = ImageDraw.Draw(image)
            
            # Draw patterns
            draw.rectangle([(0, 0), (width-1, height-1)], outline=0)  # Border
            draw.rectangle([(10, 10), (width//2-10, height//2-10)], fill=0)  # Black rectangle
            draw.line([(0, 0), (width-1, height-1)], fill=0, width=5)  # Diagonal line
            draw.line([(0, height-1), (width-1, 0)], fill=0, width=5)  # Diagonal line
            
            # Convert to buffer format
            pixels = image.load()
            buffer = []
            
            for y in range(0, height, 8):
                for x in range(width):
                    byte = 0
                    for bit in range(8):
                        if y + bit < height:
                            if pixels[x, y + bit] == 0:  # Black
                                byte |= (1 << bit)
                    buffer.append(byte)
            
            # Send buffer to display
            self.send_command(0x13)  # DATA_START_TRANSMISSION_2
            self.send_data(buffer)
            
            # Refresh display
            self.send_command(0x12)  # DISPLAY_REFRESH
            time.sleep(0.1)
            self.wait_busy(timeout=15)
            
            logger.info("Test pattern displayed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to display test pattern: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def run_full_test(self):
        """Run full diagnostics test sequence"""
        logger.info("=== Starting E-Ink Display Diagnostics ===")
        
        success = True
        
        try:
            # Step 1: Set up hardware
            logger.info("Step 1: Setting up hardware")
            if not self.setup_hardware():
                logger.error("Hardware setup failed")
                return False
                
            # Step 2: Initialize display
            logger.info("Step 2: Initializing display")
            if not self.initialize_display():
                logger.error("Display initialization failed")
                success = False
            
            # Step 3: Clear display
            logger.info("Step 3: Clearing display")
            if not self.clear_display():
                logger.error("Display clear failed")
                success = False
            
            # Step 4: Display test pattern
            logger.info("Step 4: Displaying test pattern")
            if not self.display_test_pattern():
                logger.error("Test pattern display failed")
                success = False
                
            # Final result
            if success:
                logger.info("=== E-Ink Display Diagnostics PASSED ===")
            else:
                logger.error("=== E-Ink Display Diagnostics FAILED ===")
                
            return success
        except Exception as e:
            logger.error(f"Diagnostic test failed with error: {e}")
            logger.error(traceback.format_exc())
            return False
        finally:
            # Always clean up hardware resources
            self.cleanup()

def main():
    """Main entry point"""
    try:
        # Run diagnostics
        diag = EInkDiagnostics()
        result = diag.run_full_test()
        
        # Return appropriate exit code
        return 0 if result else 1
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 