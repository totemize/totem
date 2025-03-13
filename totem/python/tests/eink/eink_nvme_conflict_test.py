#!/usr/bin/env python3
"""
E-Ink and NVMe Conflict Test
This script tests for conflicts between the NVMe HAT and E-Ink display
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import hardware libraries
try:
    import RPi.GPIO as GPIO
    import spidev
    HARDWARE_AVAILABLE = True
    logger.info("Hardware libraries successfully imported")
except ImportError as e:
    HARDWARE_AVAILABLE = False
    logger.error(f"Error importing hardware libraries: {e}")
    logger.error("Make sure spidev and RPi.GPIO are installed")

# Original E-Ink pins
EINK_RST_PIN = 17
EINK_DC_PIN = 25
EINK_BUSY_PIN = 24
EINK_CS_PIN = 8

# Alternative pins for testing
ALT_RST_PIN = 27
ALT_DC_PIN = 22
ALT_BUSY_PIN = 23
ALT_CS_PIN = 7

def run_command(cmd):
    """Run a shell command and return the output"""
    logger.info(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stdout:
            logger.info(f"OUTPUT: {result.stdout}")
        if result.stderr:
            logger.warning(f"ERRORS: {result.stderr}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            logger.info(f"OUTPUT: {e.stdout}")
        if e.stderr:
            logger.warning(f"ERRORS: {e.stderr}")
        return None

def check_nvme_status():
    """Check NVMe status and mounted partitions"""
    logger.info("=== Checking NVMe Status ===")
    
    # Check if NVMe device exists
    nvme_devices = run_command("ls -la /dev/nvme* 2>/dev/null || echo 'No NVMe devices found'")
    
    # Check mounted partitions
    mount_info = run_command("mount | grep nvme || echo 'No NVMe partitions mounted'")
    
    # Check disk space
    disk_space = run_command("df -h | grep nvme || echo 'No NVMe partitions in df output'")
    
    return nvme_devices is not None and "No NVMe devices found" not in nvme_devices

def test_gpio_pin(pin_num, pin_name):
    """Test if a GPIO pin is usable"""
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, skipping GPIO test")
        return False
    
    logger.info(f"Testing {pin_name} pin (GPIO {pin_num})")
    
    try:
        # Set up the pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_num, GPIO.OUT)
        
        # Toggle the pin a few times
        for i in range(3):
            GPIO.output(pin_num, GPIO.HIGH)
            time.sleep(0.1)
            high_state = GPIO.input(pin_num)
            
            GPIO.output(pin_num, GPIO.LOW)
            time.sleep(0.1)
            low_state = GPIO.input(pin_num)
            
            logger.info(f"  Toggle {i+1}: HIGH read as {high_state}, LOW read as {low_state}")
        
        # Clean up
        GPIO.cleanup(pin_num)
        
        # If we got here without errors, the pin is usable
        logger.info(f"  {pin_name} pin (GPIO {pin_num}) is usable")
        return True
    
    except Exception as e:
        logger.error(f"Error testing {pin_name} pin (GPIO {pin_num}): {e}")
        try:
            GPIO.cleanup(pin_num)
        except:
            pass
        return False

def test_spi_device(bus, device):
    """Test if an SPI device is usable"""
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, skipping SPI test")
        return False
    
    logger.info(f"Testing SPI bus {bus}, device {device}")
    
    try:
        # Open SPI device
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.max_speed_hz = 1000000
        spi.mode = 0
        
        # Try to transfer some data
        test_data = [0xAA, 0x55, 0xAA, 0x55]
        result = spi.xfer2(test_data)
        
        logger.info(f"  SPI transfer test: sent {test_data}, received {result}")
        
        # Close SPI device
        spi.close()
        
        # If we got here without errors, the SPI device is usable
        logger.info(f"  SPI bus {bus}, device {device} is usable")
        return True
    
    except Exception as e:
        logger.error(f"Error testing SPI bus {bus}, device {device}: {e}")
        try:
            spi.close()
        except:
            pass
        return False

def test_eink_pins(use_alt_pins=False):
    """Test all E-Ink pins"""
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, skipping E-Ink pin tests")
        return False
    
    if use_alt_pins:
        logger.info("=== Testing Alternative E-Ink Pins ===")
        rst_pin = ALT_RST_PIN
        dc_pin = ALT_DC_PIN
        busy_pin = ALT_BUSY_PIN
        cs_pin = ALT_CS_PIN
    else:
        logger.info("=== Testing Original E-Ink Pins ===")
        rst_pin = EINK_RST_PIN
        dc_pin = EINK_DC_PIN
        busy_pin = EINK_BUSY_PIN
        cs_pin = EINK_CS_PIN
    
    # Test each pin
    rst_ok = test_gpio_pin(rst_pin, "RST")
    dc_ok = test_gpio_pin(dc_pin, "DC")
    
    # BUSY pin is an input, so test it differently
    logger.info(f"Testing BUSY pin (GPIO {busy_pin})")
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(busy_pin, GPIO.IN)
        busy_state = GPIO.input(busy_pin)
        logger.info(f"  BUSY pin state: {busy_state}")
        GPIO.cleanup(busy_pin)
        busy_ok = True
    except Exception as e:
        logger.error(f"Error testing BUSY pin (GPIO {busy_pin}): {e}")
        try:
            GPIO.cleanup(busy_pin)
        except:
            pass
        busy_ok = False
    
    # CS pin test
    cs_ok = test_gpio_pin(cs_pin, "CS")
    
    # Return True if all pins are OK
    return rst_ok and dc_ok and busy_ok and cs_ok

def test_eink_spi(use_alt_spi=False):
    """Test E-Ink SPI communication"""
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, skipping E-Ink SPI tests")
        return False
    
    if use_alt_spi:
        logger.info("=== Testing Alternative SPI Device (0.1) ===")
        bus = 0
        device = 1
    else:
        logger.info("=== Testing Original SPI Device (0.0) ===")
        bus = 0
        device = 0
    
    return test_spi_device(bus, device)

def run_nvme_test():
    """Run a simple NVMe test"""
    logger.info("=== Running NVMe Test ===")
    
    # Check if NVMe is available
    if not check_nvme_status():
        logger.error("NVMe device not found, skipping test")
        return False
    
    # Try to write and read from NVMe
    test_file = "/mnt/nvme/eink_nvme_test.txt"
    test_content = f"Test data: {time.time()}"
    
    # Make sure mount point exists
    run_command("sudo mkdir -p /mnt/nvme")
    
    # Try to mount NVMe if not already mounted
    run_command("mount | grep nvme || sudo mount /dev/nvme0n1p3 /mnt/nvme")
    
    # Write test file
    logger.info(f"Writing test file to {test_file}")
    write_cmd = f"echo '{test_content}' | sudo tee {test_file}"
    write_result = run_command(write_cmd)
    
    # Read test file
    logger.info(f"Reading test file from {test_file}")
    read_cmd = f"sudo cat {test_file}"
    read_result = run_command(read_cmd)
    
    # Verify content
    if read_result and test_content in read_result:
        logger.info("NVMe read/write test passed")
        return True
    else:
        logger.error("NVMe read/write test failed")
        return False

def run_eink_gpio_test(use_alt_pins=False):
    """Run E-Ink GPIO test with original or alternative pins"""
    if use_alt_pins:
        logger.info("=== Running E-Ink GPIO Test with Alternative Pins ===")
        pins_ok = test_eink_pins(use_alt_pins=True)
    else:
        logger.info("=== Running E-Ink GPIO Test with Original Pins ===")
        pins_ok = test_eink_pins(use_alt_pins=False)
    
    return pins_ok

def run_eink_spi_test(use_alt_spi=False):
    """Run E-Ink SPI test with original or alternative SPI device"""
    if use_alt_spi:
        logger.info("=== Running E-Ink SPI Test with Alternative SPI Device ===")
        spi_ok = test_eink_spi(use_alt_spi=True)
    else:
        logger.info("=== Running E-Ink SPI Test with Original SPI Device ===")
        spi_ok = test_eink_spi(use_alt_spi=False)
    
    return spi_ok

def run_concurrent_test():
    """Run NVMe and E-Ink tests concurrently to check for conflicts"""
    logger.info("=== Running Concurrent NVMe and E-Ink Tests ===")
    
    # First run NVMe test
    nvme_ok = run_nvme_test()
    
    # Then immediately run E-Ink tests
    eink_gpio_ok = run_eink_gpio_test()
    eink_spi_ok = run_eink_spi_test()
    
    # Try alternative pins if original pins fail
    if not eink_gpio_ok:
        logger.warning("Original E-Ink pins test failed, trying alternative pins")
        eink_alt_gpio_ok = run_eink_gpio_test(use_alt_pins=True)
    else:
        eink_alt_gpio_ok = True
    
    # Try alternative SPI if original SPI fails
    if not eink_spi_ok:
        logger.warning("Original E-Ink SPI test failed, trying alternative SPI")
        eink_alt_spi_ok = run_eink_spi_test(use_alt_spi=True)
    else:
        eink_alt_spi_ok = True
    
    # Report results
    logger.info("=== Concurrent Test Results ===")
    logger.info(f"NVMe Test: {'PASS' if nvme_ok else 'FAIL'}")
    logger.info(f"E-Ink GPIO Test (Original Pins): {'PASS' if eink_gpio_ok else 'FAIL'}")
    logger.info(f"E-Ink SPI Test (Original Device): {'PASS' if eink_spi_ok else 'FAIL'}")
    
    if not eink_gpio_ok:
        logger.info(f"E-Ink GPIO Test (Alternative Pins): {'PASS' if eink_alt_gpio_ok else 'FAIL'}")
    
    if not eink_spi_ok:
        logger.info(f"E-Ink SPI Test (Alternative Device): {'PASS' if eink_alt_spi_ok else 'FAIL'}")
    
    # Determine if there's a conflict
    if nvme_ok and (eink_gpio_ok or eink_alt_gpio_ok) and (eink_spi_ok or eink_alt_spi_ok):
        logger.info("No conflict detected between NVMe and E-Ink")
        return True
    else:
        logger.warning("Potential conflict detected between NVMe and E-Ink")
        return False

def main():
    """Main function"""
    logger.info("=== E-Ink and NVMe Conflict Test ===")
    
    if not HARDWARE_AVAILABLE:
        logger.error("Hardware libraries not available, exiting")
        return 1
    
    try:
        # Clean up any existing GPIO setup
        GPIO.cleanup()
        
        # Check NVMe status
        nvme_available = check_nvme_status()
        logger.info(f"NVMe Status: {'Available' if nvme_available else 'Not Available'}")
        
        # Run concurrent test
        conflict_free = run_concurrent_test()
        
        # Final cleanup
        GPIO.cleanup()
        
        if conflict_free:
            logger.info("=== Test Completed: No Conflicts Detected ===")
            logger.info("If the E-Ink display is still not working, the issue may be with the display itself or its connection.")
            return 0
        else:
            logger.warning("=== Test Completed: Potential Conflicts Detected ===")
            logger.warning("Try using the alternative pins and SPI device for the E-Ink display.")
            return 1
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        GPIO.cleanup()
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        GPIO.cleanup()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 