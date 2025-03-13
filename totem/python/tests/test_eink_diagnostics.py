#!/usr/bin/env python3
"""
Diagnostic test script for EInk display
Tests individual functions of the EInk display to isolate issues
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Add the parent directory to path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
totem_dir = os.path.dirname(python_dir)
sys.path.insert(0, totem_dir)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("eink_diagnostics")

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)

def test_init_only():
    """Test just initializing the EInk display"""
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    print_section("Testing initialization only")
    logger.info("Creating EInk display object")
    epd = WaveshareEPD3in7()
    
    logger.info("Initializing display")
    epd.init()
    
    logger.info("Closing display")
    epd.close()
    
    logger.info("Initialization test completed")
    return True

def test_gpio_pins():
    """Test which GPIO pins are busy or free"""
    print_section("Testing GPIO pins")
    
    try:
        import lgpio
        logger.info("Using lgpio to test GPIO pins")
        
        # Open GPIO chip
        h = lgpio.gpiochip_open(0)
        logger.info("Successfully opened GPIO chip")
        
        # Test each pin
        busy_pins = []
        free_pins = []
        
        for pin in range(0, 28):  # Raspberry Pi has GPIO pins 0-27
            try:
                # Try to claim the pin as output
                lgpio.gpio_claim_output(h, pin, 0)
                logger.info(f"Pin {pin} is free")
                free_pins.append(pin)
                
                # Free the pin
                lgpio.gpio_free(h, pin)
            except Exception as e:
                logger.warning(f"Pin {pin} is busy: {e}")
                busy_pins.append(pin)
        
        # Close GPIO chip
        lgpio.gpiochip_close(h)
        
        logger.info(f"Free pins: {free_pins}")
        logger.info(f"Busy pins: {busy_pins}")
        
        return True
    except Exception as e:
        logger.error(f"GPIO test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_digital_write_read():
    """Test digital write and read operations on GPIO pins"""
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    print_section("Testing digital write/read")
    
    # Use a pin we know is free
    test_pin = int(os.environ.get('EINK_TEST_PIN', 22))  # Default to pin 22
    logger.info(f"Testing digital write/read on pin {test_pin}")
    
    epd = WaveshareEPD3in7()
    
    # Test writing and reading a pin without full init
    logger.info(f"Opening GPIO")
    if hasattr(epd, 'gpio_handle') and epd.gpio_handle is None:
        import lgpio
        epd.gpio_handle = lgpio.gpiochip_open(0)
        logger.info(f"GPIO chip opened")
    
    # Write high
    logger.info(f"Writing HIGH to pin {test_pin}")
    epd._digital_write(test_pin, 1)
    time.sleep(0.1)
    
    # Read back
    logger.info(f"Reading from pin {test_pin}")
    value = epd._digital_read(test_pin)
    logger.info(f"Read value: {value}")
    
    # Write low
    logger.info(f"Writing LOW to pin {test_pin}")
    epd._digital_write(test_pin, 0)
    time.sleep(0.1)
    
    # Read back
    logger.info(f"Reading from pin {test_pin}")
    value = epd._digital_read(test_pin)
    logger.info(f"Read value: {value}")
    
    # Clean up
    epd.close()
    logger.info("Digital write/read test completed")
    return True

def test_reset_only():
    """Test just the reset function of the EInk display"""
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    print_section("Testing reset only")
    epd = WaveshareEPD3in7()
    
    # Just test the reset function
    logger.info("Resetting display")
    epd.reset()
    
    # Clean up
    epd.close()
    logger.info("Reset test completed")
    return True

def test_busy_pin():
    """Test the busy pin of the EInk display"""
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7, BUSY_PIN
    
    print_section("Testing busy pin")
    epd = WaveshareEPD3in7()
    
    # Just test the busy pin
    logger.info(f"Reading busy pin (GPIO {BUSY_PIN})")
    
    # Open GPIO if needed
    if hasattr(epd, 'gpio_handle') and epd.gpio_handle is None:
        import lgpio
        epd.gpio_handle = lgpio.gpiochip_open(0)
        logger.info(f"GPIO chip opened")
    
    # Configure busy pin
    if hasattr(epd, 'pin_handles') and BUSY_PIN not in epd.pin_handles:
        import lgpio
        handle = lgpio.gpio_claim_input(epd.gpio_handle, BUSY_PIN)
        epd.pin_handles[BUSY_PIN] = handle
        logger.info(f"Configured BUSY_PIN ({BUSY_PIN}) as input")
    
    # Read busy pin
    value = epd._digital_read(BUSY_PIN)
    logger.info(f"Busy pin value: {value} (0=busy, 1=ready)")
    
    # Clean up
    epd.close()
    logger.info("Busy pin test completed")
    return True

def test_full_cycle():
    """Test a full cycle of the EInk display"""
    from python.devices.eink.waveshare_3in7 import WaveshareEPD3in7
    
    print_section("Testing full display cycle")
    epd = WaveshareEPD3in7()
    
    logger.info("Initializing display")
    epd.init()
    
    logger.info("Clearing display")
    epd.Clear()
    
    logger.info("Displaying text")
    epd.display_text("Diagnostic Test", 10, 10, 36)
    
    logger.info("Sleeping display")
    epd.sleep()
    
    logger.info("Closing display")
    epd.close()
    
    logger.info("Full cycle test completed")
    return True

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='EInk display diagnostics')
    parser.add_argument('--pin', type=int, default=9,
                      help='CS Pin to use for the EInk display')
    parser.add_argument('--test', choices=['all', 'init', 'gpio', 'write', 'reset', 'busy', 'full'],
                      default='all', help='Which test to run')
    
    args = parser.parse_args()
    
    # Set environment variables for alternative pins
    os.environ['USE_ALT_EINK_PINS'] = '1'
    os.environ['EINK_CS_PIN'] = str(args.pin)
    os.environ['USE_SW_SPI'] = '1'
    os.environ['EINK_TEST_PIN'] = str(args.pin)  # Use the same pin for testing
    
    logger.info(f"Starting EInk diagnostics with CS_PIN={args.pin}")
    logger.info(f"Python path: {sys.path}")
    
    if args.test == 'all' or args.test == 'gpio':
        if not test_gpio_pins():
            logger.error("GPIO pin test failed")
            return False
    
    if args.test == 'all' or args.test == 'init':
        if not test_init_only():
            logger.error("Initialization test failed")
            return False
    
    if args.test == 'all' or args.test == 'write':
        if not test_digital_write_read():
            logger.error("Digital write/read test failed")
            return False
    
    if args.test == 'all' or args.test == 'reset':
        if not test_reset_only():
            logger.error("Reset test failed")
            return False
    
    if args.test == 'all' or args.test == 'busy':
        if not test_busy_pin():
            logger.error("Busy pin test failed")
            return False
    
    if args.test == 'all' or args.test == 'full':
        if not test_full_cycle():
            logger.error("Full cycle test failed")
            return False
    
    logger.info("All tests completed successfully")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 