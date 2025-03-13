#!/usr/bin/env python3
"""
Test script to check which GPIO pins are busy
"""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gpio_test")

def test_gpio_pins():
    """Test which GPIO pins are busy"""
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
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting GPIO pin test")
    success = test_gpio_pins()
    if success:
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed")
    sys.exit(0 if success else 1) 