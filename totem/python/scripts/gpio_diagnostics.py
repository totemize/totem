#!/usr/bin/env python3
"""
GPIO Diagnostics Script

This script diagnoses GPIO access issues by:
1. Checking GPIO permissions
2. Identifying processes using GPIO pins
3. Attempting to access GPIO pins
4. Providing a detailed report
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("gpio_diagnostics")

# Define important GPIO pins for e-ink display
EINK_PINS = {
    "RESET": 17,
    "DC": 25,
    "BUSY": 24,
    "CS": 8
}

def check_user_permissions():
    """Check if the current user has permissions to access GPIO"""
    logger.info("Checking user permissions")
    
    user_id = os.getuid()
    user_name = subprocess.check_output(["whoami"]).decode().strip()
    
    logger.info(f"Running as user: {user_name} (UID: {user_id})")
    
    # Check if user is in gpio group
    groups = subprocess.check_output(["groups"]).decode().strip()
    logger.info(f"User groups: {groups}")
    
    if "gpio" in groups:
        logger.info("User is in the gpio group")
    else:
        logger.warning("User is NOT in the gpio group - this may cause permission issues")
    
    # Check permissions on GPIO devices
    gpio_devices = ["/dev/gpiochip0", "/dev/gpiomem"]
    for device in gpio_devices:
        if os.path.exists(device):
            try:
                stat_info = os.stat(device)
                mode = stat_info.st_mode
                owner = stat_info.st_uid
                group = stat_info.st_gid
                
                owner_name = subprocess.check_output(["id", "-un", str(owner)]).decode().strip()
                group_name = subprocess.check_output(["id", "-gn", str(group)]).decode().strip()
                
                logger.info(f"{device}: mode={oct(mode)}, owner={owner_name}, group={group_name}")
                
                # Check if user can read/write
                if os.access(device, os.R_OK | os.W_OK):
                    logger.info(f"User has read/write access to {device}")
                else:
                    logger.warning(f"User does NOT have read/write access to {device}")
            except Exception as e:
                logger.error(f"Error checking {device}: {e}")
        else:
            logger.warning(f"{device} does not exist")
    
    return

def check_processes_using_gpio():
    """Check what processes are using GPIO resources"""
    logger.info("Checking processes using GPIO resources")
    
    # Use lsof to check what's using gpiochip0
    try:
        result = subprocess.run(["sudo", "lsof", "/dev/gpiochip0"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Processes using /dev/gpiochip0:")
            for line in result.stdout.strip().split('\n'):
                logger.info(line)
        else:
            logger.warning("No processes found using /dev/gpiochip0 or lsof command failed")
            logger.info(f"lsof stderr: {result.stderr}")
    except Exception as e:
        logger.error(f"Error checking processes using GPIO: {e}")
    
    # Check for Python processes that might be using GPIO
    try:
        result = subprocess.run(["ps", "aux", "|", "grep", "python"], shell=True, capture_output=True, text=True)
        logger.info("Python processes that might be using GPIO:")
        for line in result.stdout.strip().split('\n'):
            if "python" in line.lower() and "grep" not in line:
                logger.info(line)
    except Exception as e:
        logger.error(f"Error checking Python processes: {e}")
    
    return

def test_gpio_access():
    """Test direct GPIO access using various methods"""
    logger.info("Testing GPIO access with different methods")
    
    # Test 1: gpiod library
    logger.info("Test 1: gpiod library")
    try:
        import gpiod
        logger.info("Successfully imported gpiod")
        
        # Try to get chip info
        chip_names = gpiod.chip_names()
        logger.info(f"Available GPIO chips: {chip_names}")
        
        # Try to open chip and get info
        for chip_name in chip_names:
            try:
                chip = gpiod.Chip(chip_name)
                logger.info(f"Opened chip {chip_name}: lines={chip.num_lines()}")
                chip.close()
            except Exception as e:
                logger.error(f"Error opening chip {chip_name}: {e}")
        
        # Test access to specific e-ink pins
        chip = gpiod.Chip("gpiochip0")
        logger.info("Testing access to e-ink pins:")
        
        for name, pin in EINK_PINS.items():
            try:
                line = chip.get_line(pin)
                logger.info(f"Pin {name} ({pin}): Got line")
                
                # Try to request as output (don't actually set value)
                try:
                    line.request(consumer=f"gpio_test_{name}", type=gpiod.LINE_REQ_DIR_OUT, flags=0)
                    logger.info(f"Pin {name} ({pin}): Successfully requested as output")
                    line.release()
                except Exception as e:
                    logger.warning(f"Pin {name} ({pin}): Could not request as output: {e}")
                
                # Try to request as input
                try:
                    line.request(consumer=f"gpio_test_{name}", type=gpiod.LINE_REQ_DIR_IN, flags=0)
                    value = line.get_value()
                    logger.info(f"Pin {name} ({pin}): Successfully requested as input, value={value}")
                    line.release()
                except Exception as e:
                    logger.warning(f"Pin {name} ({pin}): Could not request as input: {e}")
                    
            except Exception as e:
                logger.error(f"Error accessing pin {name} ({pin}): {e}")
        
        chip.close()
        
    except ImportError:
        logger.error("gpiod library not available")
    except Exception as e:
        logger.error(f"Error testing gpiod: {e}")
    
    return

def test_with_mock_driver():
    """Test if e-ink driver works in mock mode"""
    logger.info("Testing e-ink driver in mock mode")
    
    try:
        # Try to import display manager and initialize it
        sys.path.append(str(Path(__file__).resolve().parent.parent))
        from managers.display_manager import DisplayManager
        
        logger.info("Successfully imported DisplayManager")
        
        # Initialize with explicit mock mode
        os.environ["MOCK_EINK"] = "1"
        dm = DisplayManager()
        logger.info("Successfully initialized DisplayManager in mock mode")
        
        # Try basic operations
        dm.clear_screen()
        logger.info("Successfully cleared screen in mock mode")
        
        dm.display_text("GPIO TEST")
        logger.info("Successfully displayed text in mock mode")
        
    except Exception as e:
        logger.error(f"Error testing with mock driver: {e}")
    
    return

def diagnose_and_fix():
    """Diagnose and suggest fixes for common GPIO issues"""
    logger.info("Diagnosing GPIO issues and suggesting fixes")
    
    # Diagnosis results
    issues = []
    
    # Check for common issues
    
    # 1. Check if gpiod is installed
    try:
        import gpiod
    except ImportError:
        issues.append("gpiod Python library is not installed")
    
    # 2. Check if spidev is installed
    try:
        import spidev
    except ImportError:
        issues.append("spidev Python library is not installed")
    
    # 3. Check if user has permissions
    user_id = os.getuid()
    if user_id != 0:  # Not running as root
        groups = subprocess.check_output(["groups"]).decode().strip()
        if "gpio" not in groups and "spi" not in groups:
            issues.append("User is not in gpio or spi groups")
    
    # 4. Check if GPIO devices exist
    if not os.path.exists("/dev/gpiochip0"):
        issues.append("/dev/gpiochip0 does not exist - GPIO driver may not be loaded")
    
    if not os.path.exists("/dev/spidev0.0"):
        issues.append("/dev/spidev0.0 does not exist - SPI driver may not be loaded")
    
    # 5. Check for processes using GPIO
    try:
        result = subprocess.run(["sudo", "lsof", "/dev/gpiochip0"], capture_output=True, text=True)
        if result.returncode == 0 and len(result.stdout.strip()) > 0:
            processes = result.stdout.count('\n') - 1  # Subtract header line
            if processes > 1:  # More than one process is using GPIO
                issues.append(f"Multiple processes ({processes}) are using GPIO, which may cause conflicts")
    except Exception:
        pass
    
    # Report issues and suggest fixes
    if issues:
        logger.warning("Found the following issues:")
        for i, issue in enumerate(issues, 1):
            logger.warning(f"{i}. {issue}")
        
        logger.info("\nSuggested fixes:")
        
        for issue in issues:
            if "not installed" in issue:
                if "gpiod" in issue:
                    logger.info("- Install gpiod: sudo apt install python3-gpiod libgpiod-dev")
                if "spidev" in issue:
                    logger.info("- Install spidev: sudo apt install python3-spidev")
            
            if "not in gpio or spi groups" in issue:
                logger.info("- Add user to gpio group: sudo usermod -a -G gpio,spi $USER")
                logger.info("  Then log out and log back in for changes to take effect")
            
            if "does not exist" in issue and "GPIO driver" in issue:
                logger.info("- Enable GPIO in /boot/config.txt and reboot")
                logger.info("  Make sure dtoverlay for GPIO is properly configured")
            
            if "does not exist" in issue and "SPI driver" in issue:
                logger.info("- Enable SPI: sudo raspi-config → Interface Options → SPI → Enable")
                logger.info("  Or add 'dtparam=spi=on' to /boot/config.txt and reboot")
            
            if "Multiple processes" in issue:
                logger.info("- Identify and stop other processes using GPIO:")
                logger.info("  sudo lsof /dev/gpiochip0")
                logger.info("  Then kill those processes: sudo kill -9 <PID>")
    else:
        logger.info("No common GPIO issues detected. The problem might be more specific.")
        logger.info("Try rebooting the system to reset all GPIO and SPI state.")
    
    return

def main():
    """Main diagnostic function"""
    logger.info("Starting GPIO diagnostics")
    logger.info("-" * 50)
    
    check_user_permissions()
    logger.info("-" * 50)
    
    check_processes_using_gpio()
    logger.info("-" * 50)
    
    test_gpio_access()
    logger.info("-" * 50)
    
    test_with_mock_driver()
    logger.info("-" * 50)
    
    diagnose_and_fix()
    logger.info("-" * 50)
    
    logger.info("GPIO diagnostics complete")

if __name__ == "__main__":
    main() 