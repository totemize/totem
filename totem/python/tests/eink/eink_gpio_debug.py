#!/usr/bin/env python3
"""
E-Ink GPIO Debug Script for Raspberry Pi 5
This script tests individual GPIO pins using gpiod to diagnose issues with the E-Ink display.
It supports both gpiod v1 and v2 APIs.
"""

import os
import sys
import time
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("eink_gpio_debug")

def test_gpiod_install():
    """Test the gpiod installation"""
    logger.info("=== Testing gpiod Installation ===")
    
    try:
        import gpiod
        
        # Check the version of gpiod
        version = getattr(gpiod, 'version_string', lambda: 'Unavailable')()
        logger.info(f"gpiod version: {version}")
        
        # Determine if we're using v1 or v2 API
        has_v2_api = False
        try:
            from gpiod.line_settings import LineSettings
            has_v2_api = True
            logger.info("Detected gpiod v2 API (LineSettings is available)")
        except ImportError:
            logger.info("Detected gpiod v1 API (LineSettings not available)")
        
        return True, version, has_v2_api
    except ImportError as e:
        logger.error(f"gpiod import error: {e}")
        return False, None, False
    except Exception as e:
        logger.error(f"gpiod error: {e}")
        return False, None, False

def check_gpio_device():
    """Check if GPIO device exists and has correct permissions"""
    logger.info("=== Checking GPIO Device ===")
    
    gpio_chip_path = '/dev/gpiochip0'
    
    if os.path.exists(gpio_chip_path):
        logger.info(f"✅ GPIO device {gpio_chip_path} exists")
        
        # Check permissions
        permissions = oct(os.stat(gpio_chip_path).st_mode)
        logger.info(f"GPIO device permissions: {permissions}")
        
        # Check group ownership
        try:
            import pwd
            import grp
            stat_info = os.stat(gpio_chip_path)
            uid = stat_info.st_uid
            gid = stat_info.st_gid
            user = pwd.getpwuid(uid).pw_name
            group = grp.getgrgid(gid).gr_name
            logger.info(f"GPIO device owned by {user}:{group}")
            
            # Check if current user is in that group
            current_user = pwd.getpwuid(os.getuid()).pw_name
            user_groups = [g.gr_name for g in grp.getgrall() if current_user in g.gr_mem]
            logger.info(f"Current user ({current_user}) is in groups: {', '.join(user_groups)}")
            
            if group in user_groups:
                logger.info(f"✅ User {current_user} is in the {group} group")
            else:
                logger.warning(f"⚠️ User {current_user} is NOT in the {group} group")
        except Exception as e:
            logger.error(f"Error checking groups: {e}")
        
        return True
    else:
        logger.error(f"❌ GPIO device {gpio_chip_path} not found")
        return False

def check_gpio_processes():
    """Check if any processes are using GPIO"""
    logger.info("=== Checking Processes Using GPIO ===")
    
    try:
        import subprocess
        
        # Try using lsof to see what's using the GPIO device
        try:
            result = subprocess.run(["sudo", "lsof", "/dev/gpiochip0"], 
                                    capture_output=True, text=True, check=True)
            if result.stdout:
                logger.info(f"Processes using GPIO:\n{result.stdout}")
            else:
                logger.info("No processes found using GPIO")
                
        except subprocess.CalledProcessError:
            logger.warning("Failed to run lsof command")
        
        # Check for pigpio daemon
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if "pigpiod" in result.stdout:
            logger.warning("pigpio daemon is running and may be using GPIO pins")
        
        return True
    except Exception as e:
        logger.error(f"Error checking GPIO processes: {e}")
        return False

def test_individual_pins_v1(pins):
    """Test each GPIO pin individually using gpiod v1 API"""
    logger.info("=== Testing Individual GPIO Pins (v1 API) ===")
    
    results = {}
    
    try:
        import gpiod
        
        # Open chip
        chip = gpiod.Chip('/dev/gpiochip0')
        logger.info(f"Successfully opened chip: {chip.name}")
        
        # For each pin, try to request as both input and output
        for name, pin in pins.items():
            logger.info(f"Testing pin {name} (GPIO {pin})")
            
            # Try as output
            try:
                line = chip.get_line(pin)
                line.request(consumer=f"test-{name}", type=gpiod.LINE_REQ_DIR_OUT)
                logger.info(f"✅ Successfully requested pin {name} as OUTPUT")
                
                # Try setting values
                logger.info(f"Setting pin {name} HIGH")
                line.set_value(1)
                time.sleep(0.1)
                
                logger.info(f"Setting pin {name} LOW")
                line.set_value(0)
                time.sleep(0.1)
                
                # Release the line
                line.release()
                logger.info(f"Released pin {name}")
                
                results[f"{name}_output"] = True
            except Exception as e:
                logger.error(f"Failed to request pin {name} as OUTPUT: {e}")
                results[f"{name}_output"] = False
            
            # Try as input
            try:
                line = chip.get_line(pin)
                line.request(consumer=f"test-{name}", type=gpiod.LINE_REQ_DIR_IN)
                logger.info(f"✅ Successfully requested pin {name} as INPUT")
                
                # Try reading value
                value = line.get_value()
                logger.info(f"Pin {name} value: {value}")
                
                # Release the line
                line.release()
                logger.info(f"Released pin {name}")
                
                results[f"{name}_input"] = True
            except Exception as e:
                logger.error(f"Failed to request pin {name} as INPUT: {e}")
                results[f"{name}_input"] = False
        
        # Close chip
        chip.close()
        logger.info("Closed GPIO chip")
        
        return results
    except Exception as e:
        logger.error(f"Error testing individual pins: {e}")
        logger.error(traceback.format_exc())
        return {}

def test_individual_pins_v2(pins):
    """Test each GPIO pin individually using gpiod v2 API"""
    logger.info("=== Testing Individual GPIO Pins (v2 API) ===")
    
    results = {}
    
    try:
        import gpiod
        from gpiod.line_settings import LineSettings
        from gpiod.line import Value, Direction, Edge, Bias
        
        # Open chip
        chip = gpiod.Chip('/dev/gpiochip0')
        logger.info(f"Successfully opened chip: /dev/gpiochip0")
        
        # For each pin, try to request as both input and output
        for name, pin in pins.items():
            logger.info(f"Testing pin {name} (GPIO {pin})")
            
            # Try as output
            output_settings = LineSettings(direction=Direction.OUTPUT)
            try:
                request = chip.request_lines({pin: output_settings}, consumer=f"test-{name}")
                logger.info(f"✅ Successfully requested pin {name} as OUTPUT")
                
                # Try setting values
                logger.info(f"Setting pin {name} HIGH")
                request.set_values({pin: Value.ACTIVE})
                time.sleep(0.1)
                
                logger.info(f"Setting pin {name} LOW")
                request.set_values({pin: Value.INACTIVE})
                time.sleep(0.1)
                
                # Release the line
                request.release()
                logger.info(f"Released pin {name}")
                
                results[f"{name}_output"] = True
            except Exception as e:
                logger.error(f"Failed to request pin {name} as OUTPUT: {e}")
                results[f"{name}_output"] = False
            
            # Try as input
            input_settings = LineSettings(direction=Direction.INPUT)
            try:
                request = chip.request_lines({pin: input_settings}, consumer=f"test-{name}")
                logger.info(f"✅ Successfully requested pin {name} as INPUT")
                
                # Try reading value
                values = request.get_values()
                if pin in values:
                    logger.info(f"Pin {name} value: {values[pin]}")
                else:
                    logger.info(f"Pin {name} value not available in return dictionary")
                
                # Release the line
                request.release()
                logger.info(f"Released pin {name}")
                
                results[f"{name}_input"] = True
            except Exception as e:
                logger.error(f"Failed to request pin {name} as INPUT: {e}")
                results[f"{name}_input"] = False
        
        # Close chip
        chip.close()
        logger.info("Closed GPIO chip")
        
        return results
    except Exception as e:
        logger.error(f"Error testing individual pins: {e}")
        logger.error(traceback.format_exc())
        return {}

def main():
    logger.info("=== Starting E-Ink GPIO Debug ===")
    
    # Pin definitions
    pins = {
        "reset": 17,
        "dc": 25,
        "busy": 24,
    }
    
    # Test gpiod installation
    gpiod_ok, version, has_v2_api = test_gpiod_install()
    if not gpiod_ok:
        logger.error("Failed to import gpiod. Please install it with:")
        logger.error("  sudo apt install python3-gpiod")
        return 1
    
    # Check GPIO device
    device_ok = check_gpio_device()
    if not device_ok:
        logger.error("GPIO device not available or accessible")
        return 1
    
    # Check for processes using GPIO
    check_gpio_processes()
    
    # Test individual pins with the appropriate API
    if has_v2_api:
        pin_results = test_individual_pins_v2(pins)
    else:
        pin_results = test_individual_pins_v1(pins)
    
    # Print summary
    logger.info("=== GPIO Debug Summary ===")
    logger.info(f"gpiod version: {version}")
    logger.info(f"API version: {'v2' if has_v2_api else 'v1'}")
    
    if pin_results:
        for name, result in pin_results.items():
            logger.info(f"{name}: {'✅ PASSED' if result else '❌ FAILED'}")
    
    logger.info("=== E-Ink GPIO Debug Complete ===")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 