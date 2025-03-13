#!/usr/bin/env python3
"""
Direct SPI test for E-Ink display
Tests basic communication with the 2.13 inch Waveshare E-Ink display
"""

import time
import sys
import os

# Try to import hardware libraries
try:
    import spidev
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
    print("Hardware libraries successfully imported")
except ImportError as e:
    HARDWARE_AVAILABLE = False
    print(f"Error importing hardware libraries: {e}")
    print("Make sure spidev and RPi.GPIO are installed")
    sys.exit(1)

# Pin definitions for 2.13 inch E-Ink display
RST_PIN = 17
DC_PIN = 25
BUSY_PIN = 24
CS_PIN = 8

# Display dimensions
WIDTH = 250
HEIGHT = 122
BYTES_PER_LINE = (WIDTH + 7) // 8

# Display commands
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
    print("Setting up GPIO pins")
    
    # Use BCM pin numbering
    GPIO.setmode(GPIO.BCM)
    
    # Setup pins as outputs/inputs
    GPIO.setup(RST_PIN, GPIO.OUT)
    GPIO.setup(DC_PIN, GPIO.OUT)
    GPIO.setup(BUSY_PIN, GPIO.IN)
    
    print("GPIO pins initialized")
    return True

def setup_spi():
    """Setup SPI interface"""
    print("Setting up SPI interface")
    
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 2000000  # 2MHz
    spi.mode = 0
    
    print("SPI interface initialized")
    return spi

def reset_display():
    """Reset the display"""
    print("Resetting display")
    
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(RST_PIN, GPIO.LOW)
    time.sleep(0.2)
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.2)
    
    print("Display reset complete")

def wait_until_idle():
    """Wait until the display is idle (BUSY pin high)"""
    print("Waiting for display to be idle", end="")
    
    while GPIO.input(BUSY_PIN) == 0:  # BUSY pin is LOW when display is busy
        print(".", end="", flush=True)
        time.sleep(0.1)
    
    print("\nDisplay is idle")

def send_command(spi, command):
    """Send command to the display"""
    GPIO.output(DC_PIN, GPIO.LOW)  # DC LOW for command
    spi.writebytes([command])
    print(f"Sent command: 0x{command:02X}")

def send_data(spi, data):
    """Send data to the display"""
    GPIO.output(DC_PIN, GPIO.HIGH)  # DC HIGH for data
    if isinstance(data, int):
        spi.writebytes([data])
        print(f"Sent data: 0x{data:02X}")
    else:
        # Write data in chunks to avoid buffer issues
        chunk_size = 1024
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            spi.writebytes(chunk)
        print(f"Sent {len(data)} bytes of data")

def init_display(spi):
    """Initialize the display"""
    print("Initializing display")
    
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
    
    print("Display initialization complete")

def set_lut(spi):
    """Set the look-up table for display refresh"""
    print("Setting LUT")
    
    # LUT for Waveshare 2.13 inch E-Paper
    lut_full_update = [
        0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11, 
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
        0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00
    ]
    
    send_command(spi, WRITE_LUT_REGISTER)
    for i in range(len(lut_full_update)):
        send_data(spi, lut_full_update[i])
    
    print("LUT set complete")

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
    print("Clearing display")
    
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
    
    print("Display cleared")

def draw_pattern(spi):
    """Draw a simple test pattern"""
    print("Drawing test pattern")
    
    # Create buffer for black/white image
    # 0 = black, 1 = white
    width_bytes = (WIDTH + 7) // 8
    buffer = [0xFF] * (width_bytes * HEIGHT)  # Start with all white
    
    # Draw a black border
    for x in range(WIDTH):
        # Top and bottom borders
        set_pixel(buffer, x, 0, 0)  # Top border (black)
        set_pixel(buffer, x, HEIGHT-1, 0)  # Bottom border (black)
    
    for y in range(HEIGHT):
        # Left and right borders
        set_pixel(buffer, 0, y, 0)  # Left border (black)
        set_pixel(buffer, WIDTH-1, y, 0)  # Right border (black)
    
    # Draw diagonal lines
    for i in range(min(WIDTH, HEIGHT)):
        set_pixel(buffer, i, i, 0)  # Top-left to bottom-right (black)
        set_pixel(buffer, WIDTH-1-i, i, 0)  # Top-right to bottom-left (black)
    
    # Set window and cursor
    set_window(spi, 0, 0, WIDTH-1, HEIGHT-1)
    set_cursor(spi, 0, 0)
    
    # Send write RAM command
    send_command(spi, WRITE_RAM)
    
    # Send pixel data
    send_data(spi, buffer)
    
    # Update display
    update_display(spi)
    
    print("Test pattern displayed")

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
    """Update the display"""
    print("Updating display")
    
    send_command(spi, DISPLAY_UPDATE_CONTROL_2)
    send_data(spi, 0xC4)
    send_command(spi, MASTER_ACTIVATION)
    send_command(spi, TERMINATE_FRAME_READ_WRITE)
    
    # Wait for display to finish updating
    wait_until_idle()
    
    print("Display updated")

def cleanup():
    """Clean up GPIO and SPI resources"""
    print("Cleaning up resources")
    GPIO.cleanup()
    print("Resources cleaned up")

def main():
    """Main function"""
    print("Starting E-Ink SPI Test for Waveshare 2.13 inch display")
    
    if not HARDWARE_AVAILABLE:
        print("Hardware libraries not available, exiting")
        return 1
    
    try:
        # Setup GPIO
        if not setup_gpio():
            print("Failed to setup GPIO")
            return 1
        
        # Setup SPI
        spi = setup_spi()
        if not spi:
            print("Failed to setup SPI")
            return 1
        
        # Initialize display
        init_display(spi)
        
        # Clear display
        clear_display(spi)
        print("Display should now be white. Press Enter to continue...")
        input()
        
        # Draw test pattern
        draw_pattern(spi)
        print("Display should now show a test pattern. Press Enter to exit...")
        input()
        
        # Clear display again before exit
        clear_display(spi)
        
        # Clean up
        spi.close()
        cleanup()
        
        print("E-Ink SPI Test completed successfully")
        return 0
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Make sure we clean up even if there's an error
        try:
            spi.close()
        except:
            pass
        cleanup()
    
    return 1

if __name__ == "__main__":
    sys.exit(main()) 