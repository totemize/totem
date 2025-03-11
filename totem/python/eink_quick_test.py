#!/usr/bin/env python3
"""
Quick E-Ink Hardware Test
Tests only GPIO pins without SPI communication to identify hardware issues
"""

import os
import sys
import time
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('eink-quick-test')

# Kill any existing Python processes
def kill_python_processes():
    try:
        logger.info("Killing any Python processes that might be using GPIO")
        subprocess.run("pkill -f python || true", shell=True)
        time.sleep(2)  # Give processes time to terminate
        return True
    except Exception as e:
        logger.error(f"Error killing processes: {e}")
        return False

# Test GPIO access
def test_gpio_access():
    try:
        import gpiod
        from gpiod.line_settings import LineSettings
        
        # GPIO pin definitions
        reset_pin = 17
        dc_pin = 25
        busy_pin = 24
        
        logger.info("Opening GPIO chip")
        chip = gpiod.Chip('/dev/gpiochip0')
        
        # Configure output pins
        output_settings = LineSettings(direction=gpiod.line.Direction.OUTPUT)
        input_settings = LineSettings(direction=gpiod.line.Direction.INPUT)
        
        # Request each pin individually and test
        success = True
        
        # Test reset pin
        try:
            logger.info(f"Requesting reset pin {reset_pin}")
            reset_request = chip.request_lines({reset_pin: output_settings}, consumer="test-reset")
            logger.info("Successfully requested reset pin")
            
            # Toggle reset pin a few times
            for i in range(3):
                reset_request.set_values({reset_pin: gpiod.line.Value.ACTIVE})
                time.sleep(0.1)
                reset_request.set_values({reset_pin: gpiod.line.Value.INACTIVE})
                time.sleep(0.1)
                
            logger.info("Reset pin test successful")
            reset_request.release()
        except Exception as e:
            logger.error(f"Reset pin test failed: {e}")
            success = False
        
        # Test DC pin
        try:
            logger.info(f"Requesting DC pin {dc_pin}")
            dc_request = chip.request_lines({dc_pin: output_settings}, consumer="test-dc")
            logger.info("Successfully requested DC pin")
            
            # Toggle DC pin a few times
            for i in range(3):
                dc_request.set_values({dc_pin: gpiod.line.Value.ACTIVE})
                time.sleep(0.1)
                dc_request.set_values({dc_pin: gpiod.line.Value.INACTIVE})
                time.sleep(0.1)
                
            logger.info("DC pin test successful")
            dc_request.release()
        except Exception as e:
            logger.error(f"DC pin test failed: {e}")
            success = False
        
        # Test busy pin
        try:
            logger.info(f"Requesting busy pin {busy_pin}")
            busy_request = chip.request_lines({busy_pin: input_settings}, consumer="test-busy")
            logger.info("Successfully requested busy pin")
            
            # Read busy pin value
            busy_values = busy_request.get_values()
            if busy_values:
                busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(busy_pin)
                logger.info(f"Busy pin current value: {busy_value}")
                logger.info("Busy pin test successful")
            else:
                logger.error("Could not read busy pin value")
                success = False
                
            busy_request.release()
        except Exception as e:
            logger.error(f"Busy pin test failed: {e}")
            success = False
        
        # Close chip
        chip.close()
        
        return success
    except Exception as e:
        logger.error(f"GPIO test failed: {e}")
        return False

# Test SPI access
def test_spi_access():
    try:
        import spidev
        
        logger.info("Opening SPI device")
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 2000000  # 2MHz
        spi.mode = 0
        
        logger.info("SPI device opened successfully")
        
        # Try sending a simple command
        try:
            logger.info("Sending test data via SPI")
            spi.writebytes([0x00])
            logger.info("SPI write successful")
            success = True
        except Exception as e:
            logger.error(f"SPI write failed: {e}")
            success = False
        
        # Close SPI
        spi.close()
        
        return success
    except Exception as e:
        logger.error(f"SPI test failed: {e}")
        return False

def main():
    """Main entry point"""
    try:
        logger.info("=== Starting Quick E-Ink Hardware Test ===")
        
        # Step 1: Kill Python processes
        kill_python_processes()
        
        # Step 2: Test GPIO access
        logger.info("Testing GPIO access")
        gpio_success = test_gpio_access()
        
        # Step 3: Test SPI access (only if GPIO successful)
        spi_success = False
        if gpio_success:
            logger.info("Testing SPI access")
            spi_success = test_spi_access()
        
        # Print results
        logger.info("=== Test Results ===")
        logger.info(f"GPIO Test: {'✅ PASSED' if gpio_success else '❌ FAILED'}")
        if gpio_success:
            logger.info(f"SPI Test: {'✅ PASSED' if spi_success else '❌ FAILED'}")
        
        logger.info("=== Quick E-Ink Hardware Test Completed ===")
        
        return 0 if (gpio_success and spi_success) else 1
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 