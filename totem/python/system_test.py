import argparse
import logging

# Configure the logger
logger = logging.getLogger(__name__)

# Add a command line argument for using the software CS driver
parser = argparse.ArgumentParser(description='Run E-Ink display test')
parser.add_argument('--use-sw-cs', action='store_true', help='Use the software CS driver for E-Ink display')
parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
args = parser.parse_args()

def run_eink_test(args):
    logger.info("Starting E-Ink display test")
    try:
        if args.use_sw_cs:
            logger.info("Using software CS driver for E-Ink display")
            try:
                from devices.eink.drivers.waveshare_2in13_pi5_sw_cs import Driver
            except ImportError:
                logger.error("Software CS driver not found. Make sure waveshare_2in13_pi5_sw_cs.py is in the drivers directory.")
                return False
        else:
            # Use the original driver
            try:
                from devices.eink.drivers.waveshare_2in13_pi5 import Driver
            except ImportError:
                logger.error("E-Ink driver not found. Make sure waveshare_2in13_pi5.py is in the drivers directory.")
                return False
        
        # Create the driver instance
        driver = Driver()
        
        # Enable debug mode if verbose is enabled
        if args.verbose:
            driver.enable_debug_mode(True)
        
        # Rest of the test remains the same...
        
        return True
    except Exception as e:
        logger.error(f"Error during E-Ink display test: {e}")
        return False 