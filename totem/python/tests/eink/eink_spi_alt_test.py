#!/usr/bin/env python3
"""
Alternative SPI test for E-Ink display
Tests basic communication with the 2.13 inch Waveshare E-Ink display
using different SPI bus settings to avoid conflicts with NVMe HAT
"""

import time
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import hardware libraries
try:
    import spidev
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
    logger.info("Hardware libraries successfully imported")
except ImportError as e:
    HARDWARE_AVAILABLE = False
    logger.error(f"Error importing hardware libraries: {e}")
    logger.error("Make sure spidev and RPi.GPIO are installed")
    sys.exit(1)

# Alternative pin definitions to avoid potential conflicts
# Original pins:
# RST_PIN = 17
# DC_PIN = 25
# BUSY_PIN = 24
# CS_PIN = 8

# Alternative pins - these can be adjusted based on available pins
RST_PIN = 27  # Changed from 17
DC_PIN = 22   # Changed from 25
BUSY_PIN = 23 # Changed from 24
CS_PIN = 7    # Changed from 8 (CE1 instead of CE0)

# Display dimensions
WIDTH = 250
HEIGHT = 122
BYTES_PER_LINE = (WIDTH + 7) // 8

# Display commands (same as original)
DRIVER_OUTPUT_CONTROL          = 0x01
BOOSTER_SOFT_START_CONTROL     = 0x0C
GATE_SCAN_START_POSITION       = 0x0F
DEEP_SLEEP_MODE                = 0x10
DATA_ENTRY_MODE_SETTING        = 0x11
SW_RESET                        = 0x12
TEMPERATURE_SENSOR_CONTROL     = 0x1A
MASTER_ACTIVATION              = 0x20
DISPLAY_UPDATE_CONTROL_1       = 0x21
DISPLAY_UPDATE_CONTROL_2       = 0x22
WRITE_RAM                      = 0x24
WRITE_VCOM_REGISTER            = 0x2C
WRITE_LUT_REGISTER             = 0x32
SET_DUMMY_LINE_PERIOD          = 0x3A
SET_GATE_TIME                  = 0x3B
BORDER_WAVEFORM_CONTROL        = 0x3C
SET_RAM_X_ADDRESS_START_END_POSITION = 0x44
SET_RAM_Y_ADDRESS_START_END_POSITION = 0x45
SET_RAM_X_ADDRESS_COUNTER      = 0x4E
SET_RAM_Y_ADDRESS_COUNTER      = 0x4F
TERMINATE_FRAME_READ_WRITE     = 0xFF

def setup_gpio():
    """Setup GPIO pins for E-Ink display"""
    logger.info("Setting up GPIO pins")
    
    # Use BCM pin numbering
    GPIO.setmode(GPIO.BCM)
    
    # Setup pins as outputs/inputs
    GPIO.setup(RST_PIN, GPIO.OUT)
    GPIO.setup(DC_PIN, GPIO.OUT)
    GPIO.setup(BUSY_PIN, GPIO.IN)
    
    # Initialize CS pin manually instead of relying on hardware CS
    GPIO.setup(CS_PIN, GPIO.OUT)
    GPIO.output(CS_PIN, GPIO.HIGH)  # CS inactive by default
    
    logger.info(f"Using alternative GPIO pins: RST={RST_PIN}, DC={DC_PIN}, BUSY={BUSY_PIN}, CS={CS_PIN}")
    return True

def setup_spi():
    """Setup SPI interface with alternative settings"""
    logger.info("Setting up SPI interface with alternative settings")
    
    # List available SPI devices
    spi_devices = [f for f in os.listdir('/dev') if f.startswith('spidev')]
    logger.info(f"Available SPI devices: {spi_devices}")
    
    # Try different SPI bus/device combinations
    # Start with SPI 0.1 (second device on bus 0) instead of 0.0
    # If that fails, try 1.0 (first device on bus 1) if available
    spi = spidev.SpiDev()
    
    try:
        # Try SPI 0, device 1 (CE1)
        logger.info("Trying SPI bus 0, device 1 (CE1)")
        spi.open(0, 1)
        logger.info("Successfully opened SPI bus 0, device 1")
    except Exception as e:
        logger.warning(f"Failed to open SPI bus 0, device 1: {e}")
        try:
            # Try SPI 1, device 0 (if available)
            logger.info("Trying SPI bus 1, device 0 (CE0)")
            spi.open(1, 0)
            logger.info("Successfully opened SPI bus 1, device 0")
        except Exception as e:
            logger.warning(f"Failed to open SPI bus 1, device 0: {e}")
            logger.info("Falling back to SPI bus 0, device 0")
            try:
                spi.open(0, 0)
                logger.info("Successfully opened SPI bus 0, device 0")
            except Exception as e:
                logger.error(f"Failed to open any SPI device: {e}")
                return None
    
    # Set SPI parameters
    spi.max_speed_hz = 1000000  # 1MHz (slower than original 2MHz for reliability)
    spi.mode = 0
    
    logger.info(f"SPI interface initialized: bus={spi.bus}, device={spi.device}, speed={spi.max_speed_hz}")
    return spi

def reset_display():
    """Reset the display with longer delays"""
    logger.info("Resetting display with extended timing")
    
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.5)  # Longer delay
    GPIO.output(RST_PIN, GPIO.LOW)
    time.sleep(0.5)  # Longer delay
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.5)  # Longer delay
    
    logger.info("Display reset complete")

def wait_until_idle():
    """Wait until the display is idle (BUSY pin high)"""
    logger.info("Waiting for display to be idle")
    
    timeout = 30  # Longer timeout (30 seconds)
    start_time = time.time()
    
    while GPIO.input(BUSY_PIN) == 0:  # BUSY pin is LOW when display is busy
        if time.time() - start_time > timeout:
            logger.warning("Timeout waiting for display to be idle")
            break
        time.sleep(0.1)
    
    logger.info("Display is idle")

def send_command(spi, command):
    """Send command to the display using software CS control"""
    GPIO.output(DC_PIN, GPIO.LOW)  # DC LOW for command
    GPIO.output(CS_PIN, GPIO.LOW)  # CS active
    spi.writebytes([command])
    GPIO.output(CS_PIN, GPIO.HIGH)  # CS inactive
    logger.info(f"Sent command: 0x{command:02X}")

def send_data(spi, data):
    """Send data to the display using software CS control"""
    GPIO.output(DC_PIN, GPIO.HIGH)  # DC HIGH for data
    GPIO.output(CS_PIN, GPIO.LOW)   # CS active
    
    if isinstance(data, int):
        spi.writebytes([data])
        logger.info(f"Sent data: 0x{data:02X}")
    else:
        # Write data in chunks to avoid buffer issues
        chunk_size = 512  # Smaller chunks for reliability
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            spi.writebytes(chunk)
            time.sleep(0.001)  # Small delay between chunks
        logger.info(f"Sent {len(data)} bytes of data")
    
    GPIO.output(CS_PIN, GPIO.HIGH)  # CS inactive

def init_display(spi):
    """Initialize the display with enhanced error reporting"""
    logger.info("Initializing display")
    
    try:
        # Reset the display
        reset_display()
        
        # Send initialization commands
        send_command(spi, DRIVER_OUTPUT_CONTROL)
        send_data(spi, 0x79)  # (HEIGHT-1) & 0xFF = 121 = 0x79
        send_data(spi, 0x00)  # ((HEIGHT-1) >> 8) & 0xFF
        send_data(spi, 0x00)  # GD=0, SM=0, TB=0
        
        send_command(spi, BOOSTER_SOFT_START_CONTROL)
        send_data(spi, 0xD7)
        send_data(spi, 0xD6)
        send_data(spi, 0x9D)
        
        send_command(spi, WRITE_VCOM_REGISTER)
        send_data(spi, 0xA8)  # VCOM 7C
        
        send_command(spi, SET_DUMMY_LINE_PERIOD)
        send_data(spi, 0x1A)  # 4 dummy lines per gate
        
        send_command(spi, SET_GATE_TIME)
        send_data(spi, 0x08)  # 2us per line
        
        send_command(spi, DATA_ENTRY_MODE_SETTING)
        send_data(spi, 0x03)  # X increment; Y increment
        
        # Set the look-up table for display refresh
        set_lut(spi)
        
        logger.info("Display initialization complete")
        return True
    except Exception as e:
        logger.error(f"Error during display initialization: {e}")
        return False

def set_lut(spi):
    """Set the look-up table for display refresh"""
    logger.info("Setting LUT")
    
    # LUT for Waveshare 2.13 inch E-Paper (full refresh)
    lut_full_update = [
        0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11, 
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
        0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00
    ]
    
    send_command(spi, WRITE_LUT_REGISTER)
    for i in range(len(lut_full_update)):
        send_data(spi, lut_full_update[i])
    
    logger.info("LUT set complete")

def set_window(spi, x_start, y_start, x_end, y_end):
    """Set window for data transmission"""
    # X position
    send_command(spi, SET_RAM_X_ADDRESS_START_END_POSITION)
    send_data(spi, (x_start >> 3) & 0xFF)
    send_data(spi, (x_end >> 3) & 0xFF)
    
    # Y position
    send_command(spi, SET_RAM_Y_ADDRESS_START_END_POSITION)
    send_data(spi, y_start & 0xFF)
    send_data(spi, (y_start >> 8) & 0xFF)
    send_data(spi, y_end & 0xFF)
    send_data(spi, (y_end >> 8) & 0xFF)

def set_cursor(spi, x, y):
    """Set cursor position for data transmission"""
    send_command(spi, SET_RAM_X_ADDRESS_COUNTER)
    send_data(spi, (x >> 3) & 0xFF)
    
    send_command(spi, SET_RAM_Y_ADDRESS_COUNTER)
    send_data(spi, y & 0xFF)
    send_data(spi, (y >> 8) & 0xFF)

def clear_display(spi):
    """Clear the display (set to white)"""
    logger.info("Clearing display")
    
    try:
        # Set window
        set_window(spi, 0, 0, WIDTH-1, HEIGHT-1)
        set_cursor(spi, 0, 0)
        
        # Send write RAM command
        send_command(spi, WRITE_RAM)
        
        # Send all white pixels (0xFF)
        white_pixels = [0xFF] * (WIDTH * HEIGHT // 8)
        send_data(spi, white_pixels)
        
        # Update display
        update_display(spi)
        
        logger.info("Display cleared")
        return True
    except Exception as e:
        logger.error(f"Error clearing display: {e}")
        return False

def draw_pattern(spi):
    """Draw a simple test pattern (solid black to ensure visibility)"""
    logger.info("Drawing test pattern (solid black)")
    
    try:
        # Create buffer for black image (all 0s)
        buffer = [0x00] * (((WIDTH + 7) // 8) * HEIGHT)  # All black (0x00)
        
        # Set window and cursor
        set_window(spi, 0, 0, WIDTH-1, HEIGHT-1)
        set_cursor(spi, 0, 0)
        
        # Send write RAM command
        send_command(spi, WRITE_RAM)
        
        # Send pixel data
        send_data(spi, buffer)
        
        # Update display
        update_display(spi)
        
        logger.info("Test pattern displayed")
        return True
    except Exception as e:
        logger.error(f"Error drawing test pattern: {e}")
        return False

def set_pixel(buffer, x, y, color):
    """Set a pixel in the buffer (0=black, 1=white)"""
    if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
        return
    
    width_bytes = (WIDTH + 7) // 8
    byte_index = (y * width_bytes) + (x // 8)
    bit_position = 7 - (x % 8)  # MSB first
    
    if color == 0:  # Black
        buffer[byte_index] &= ~(1 << bit_position)
    else:  # White
        buffer[byte_index] |= (1 << bit_position)

def update_display(spi):
    """Update the display with enhanced error handling"""
    logger.info("Updating display")
    
    try:
        send_command(spi, DISPLAY_UPDATE_CONTROL_2)
        send_data(spi, 0xC4)
        send_command(spi, MASTER_ACTIVATION)
        send_command(spi, TERMINATE_FRAME_READ_WRITE)
        
        # Wait for display to finish updating
        wait_until_idle()
        
        logger.info("Display updated")
        return True
    except Exception as e:
        logger.error(f"Error updating display: {e}")
        return False

def deep_sleep(spi):
    """Put the display in deep sleep mode"""
    logger.info("Putting display in deep sleep mode")
    
    try:
        send_command(spi, DEEP_SLEEP_MODE)
        send_data(spi, 0x01)  # Enter deep sleep
        logger.info("Display in deep sleep mode")
        return True
    except Exception as e:
        logger.error(f"Error entering deep sleep: {e}")
        return False

def cleanup():
    """Clean up GPIO and SPI resources"""
    logger.info("Cleaning up resources")
    GPIO.cleanup()
    logger.info("Resources cleaned up")

def main():
    """Main function with enhanced error handling"""
    logger.info("Starting Alternative E-Ink SPI Test for Waveshare 2.13 inch display")
    
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, exiting")
        return 1
    
    spi = None
    
    try:
        # Setup GPIO
        if not setup_gpio():
            logger.error("Failed to setup GPIO")
            return 1
        
        # Setup SPI
        spi = setup_spi()
        if not spi:
            logger.error("Failed to setup SPI")
            return 1
        
        # Initialize display
        if not init_display(spi):
            logger.error("Failed to initialize display")
            return 1
        
        # Clear display
        if not clear_display(spi):
            logger.error("Failed to clear display")
        
        logger.info("Display should now be white. Press Enter to continue...")
        input()
        
        # Draw test pattern (solid black)
        if not draw_pattern(spi):
            logger.error("Failed to draw test pattern")
        
        logger.info("Display should now be solid black. Press Enter to exit...")
        input()
        
        # Clear display again before exit
        if not clear_display(spi):
            logger.error("Failed to clear display")
        
        # Put display in deep sleep
        if not deep_sleep(spi):
            logger.error("Failed to put display in deep sleep")
        
        # Clean up
        spi.close()
        cleanup()
        
        logger.info("Alternative E-Ink SPI Test completed successfully")
        return 0
    
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Make sure we clean up even if there's an error
        if spi:
            try:
                spi.close()
            except:
                pass
        try:
            cleanup()
        except:
            pass
    
    return 1

if __name__ == "__main__":
    sys.exit(main()) 