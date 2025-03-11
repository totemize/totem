#!/usr/bin/env python3
"""
Simple GPIO Test Script for E-Ink Display
This script performs basic GPIO toggling to diagnose E-Ink display issues.
"""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('eink-test')

# Import gpiod
try:
    import gpiod
    from gpiod.line_settings import LineSettings
    logger.info("Successfully imported gpiod")
except ImportError:
    logger.error("Failed to import gpiod. Make sure it's installed.")
    sys.exit(1)

def test_gpio():
    """Test basic GPIO control for E-Ink display"""
    
    # GPIO pin definitions
    reset_pin = 17
    dc_pin = 25
    busy_pin = 24
    
    logger.info("Opening GPIO chip")
    try:
        chip = gpiod.Chip('/dev/gpiochip0')
        logger.info("Successfully opened GPIO chip")
    except Exception as e:
        logger.error(f"Failed to open GPIO chip: {e}")
        return False
    
    # Configure output pins
    output_settings = LineSettings(direction=gpiod.line.Direction.OUTPUT)
    input_settings = LineSettings(direction=gpiod.line.Direction.INPUT)
    
    # Test reset pin
    try:
        logger.info(f"Requesting reset pin {reset_pin}")
        reset_request = chip.request_lines({reset_pin: output_settings}, consumer="test-reset")
        logger.info("Successfully requested reset pin")
        
        # Toggle reset pin
        logger.info("Setting reset pin HIGH")
        reset_request.set_values({reset_pin: gpiod.line.Value.ACTIVE})
        time.sleep(0.2)
        
        logger.info("Setting reset pin LOW")
        reset_request.set_values({reset_pin: gpiod.line.Value.INACTIVE})
        time.sleep(0.2)
        
        logger.info("Setting reset pin HIGH")
        reset_request.set_values({reset_pin: gpiod.line.Value.ACTIVE})
        time.sleep(0.2)
        
        logger.info("✅ Reset pin test successful")
    except Exception as e:
        logger.error(f"❌ Reset pin test failed: {e}")
        return False
    finally:
        if 'reset_request' in locals():
            reset_request.release()
    
    # Test DC pin
    try:
        logger.info(f"Requesting DC pin {dc_pin}")
        dc_request = chip.request_lines({dc_pin: output_settings}, consumer="test-dc")
        logger.info("Successfully requested DC pin")
        
        # Toggle DC pin
        logger.info("Setting DC pin HIGH")
        dc_request.set_values({dc_pin: gpiod.line.Value.ACTIVE})
        time.sleep(0.2)
        
        logger.info("Setting DC pin LOW")
        dc_request.set_values({dc_pin: gpiod.line.Value.INACTIVE})
        time.sleep(0.2)
        
        logger.info("✅ DC pin test successful")
    except Exception as e:
        logger.error(f"❌ DC pin test failed: {e}")
        return False
    finally:
        if 'dc_request' in locals():
            dc_request.release()
    
    # Test busy pin
    try:
        logger.info(f"Requesting busy pin {busy_pin}")
        busy_request = chip.request_lines({busy_pin: input_settings}, consumer="test-busy")
        logger.info("Successfully requested busy pin")
        
        # Read busy pin
        busy_values = busy_request.get_values()
        if busy_values:
            busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(busy_pin)
            logger.info(f"Busy pin current value: {busy_value}")
            logger.info("✅ Busy pin test successful")
        else:
            logger.warning("Could not read busy pin value")
            logger.info("❌ Busy pin test failed")
            return False
    except Exception as e:
        logger.error(f"❌ Busy pin test failed: {e}")
        return False
    finally:
        if 'busy_request' in locals():
            busy_request.release()
    
    # Test SPI communication
    try:
        import spidev
        logger.info("Opening SPI device")
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 2000000
        logger.info("Successfully opened SPI device")
        
        # Send a test byte
        logger.info("Sending test byte via SPI")
        spi.writebytes([0x00])  # NOP command
        logger.info("✅ SPI test successful")
    except Exception as e:
        logger.error(f"❌ SPI test failed: {e}")
        return False
    finally:
        if 'spi' in locals():
            spi.close()
    
    logger.info("All GPIO tests completed successfully")
    return True

def main():
    """Main entry point for the GPIO test script."""
    logger.info("=== Starting Simple GPIO Test for E-Ink Display ===")
    result = test_gpio()
    if result:
        logger.info("✅ All tests PASSED")
        return 0
    else:
        logger.error("❌ Some tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 