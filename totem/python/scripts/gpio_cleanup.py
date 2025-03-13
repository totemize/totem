#!/usr/bin/env python3
"""
GPIO Cleanup Script for Raspberry Pi 5
This script attempts to release any GPIO pins that might be in use
"""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import gpiod
    GPIOD_AVAILABLE = True
    logger.info("gpiod library is available")
except ImportError:
    GPIOD_AVAILABLE = False
    logger.error("gpiod library is not available. Please install it using: pip install gpiod")
    sys.exit(1)

# Define the pins we want to check/release
TARGET_PINS = [17, 25, 24, 8]  # reset, dc, busy, cs pins

def check_gpiochip():
    """Check if gpiochip0 exists and is accessible"""
    gpiochip_path = '/dev/gpiochip0'
    if not os.path.exists(gpiochip_path):
        logger.error(f"GPIO chip not found at {gpiochip_path}")
        return False
    
    try:
        # Check permissions
        stats = os.stat(gpiochip_path)
        mode = stats.st_mode
        logger.info(f"GPIO chip permissions: {oct(mode)}")
        
        # Check ownership
        logger.info(f"GPIO chip owner: {stats.st_uid}, group: {stats.st_gid}")
        logger.info(f"Current user: {os.getuid()}, group: {os.getgid()}")
        
        return True
    except Exception as e:
        logger.error(f"Error checking GPIO chip: {e}")
        return False

def check_pin_status():
    """Check the status of target pins"""
    if not GPIOD_AVAILABLE:
        return False
    
    try:
        # Open GPIO chip
        chip = gpiod.Chip('/dev/gpiochip0')
        
        # Check each pin
        for pin in TARGET_PINS:
            try:
                # Try to get info about the line
                line_info = chip.get_line_info(pin)
                consumer = line_info.consumer
                
                if consumer:
                    logger.info(f"Pin {pin} is in use by: {consumer}")
                else:
                    logger.info(f"Pin {pin} is not in use")
                    
            except Exception as e:
                logger.error(f"Error checking pin {pin}: {e}")
        
        chip.close()
        return True
    except Exception as e:
        logger.error(f"Error opening GPIO chip: {e}")
        return False

def release_pins():
    """Attempt to release target pins"""
    if not GPIOD_AVAILABLE:
        return False
    
    try:
        # Open GPIO chip
        chip = gpiod.Chip('/dev/gpiochip0')
        
        # Check if we're using v1 or v2 API
        has_v2_api = False
        try:
            from gpiod.line_settings import LineSettings
            has_v2_api = True
            logger.info("Using gpiod v2 API")
        except ImportError:
            has_v2_api = False
            logger.info("Using gpiod v1 API")
        
        # Release each pin
        for pin in TARGET_PINS:
            try:
                if has_v2_api:
                    # V2 API
                    from gpiod.line import Direction
                    settings = gpiod.line_settings.LineSettings()
                    settings.direction = Direction.INPUT
                    
                    try:
                        request = chip.request_lines({pin: settings}, consumer="cleanup")
                        logger.info(f"Successfully claimed pin {pin}")
                        request.release()
                        logger.info(f"Released pin {pin}")
                    except Exception as e:
                        logger.warning(f"Couldn't claim pin {pin}: {e}")
                else:
                    # V1 API
                    try:
                        line = chip.get_line(pin)
                        line.request(consumer="cleanup", type=gpiod.LINE_REQ_DIR_IN)
                        logger.info(f"Successfully claimed pin {pin}")
                        line.release()
                        logger.info(f"Released pin {pin}")
                    except Exception as e:
                        logger.warning(f"Couldn't claim pin {pin}: {e}")
            except Exception as e:
                logger.error(f"Error handling pin {pin}: {e}")
        
        chip.close()
        return True
    except Exception as e:
        logger.error(f"Error opening GPIO chip: {e}")
        return False

def main():
    """Main function"""
    logger.info("=== GPIO Cleanup Script for Raspberry Pi 5 ===")
    
    # Check gpiochip
    if not check_gpiochip():
        logger.error("GPIO chip check failed")
        return 1
    
    # Check pin status
    logger.info("Checking pin status...")
    check_pin_status()
    
    # Release pins
    logger.info("Attempting to release pins...")
    release_pins()
    
    # Check status again
    logger.info("Checking pin status after release...")
    check_pin_status()
    
    logger.info("GPIO cleanup completed")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 