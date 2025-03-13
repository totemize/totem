import argparse
import logging
import os
import sys

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Configure the logger
from utils.logger import logger

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run E-Ink display test')
parser.add_argument('--use-sw-cs', action='store_true', help='Use the software CS driver for E-Ink display')
parser.add_argument('--use-service', action='store_true', help='Use the EInk service instead of direct hardware access')
parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
args = parser.parse_args()

def run_eink_test(args):
    """Test the E-Ink display functionality"""
    logger.info("Starting E-Ink display test")
    
    # Set environment variables based on args
    if args.use_service:
        os.environ['USE_EINK_SERVICE'] = '1'
        logger.info("Using EInk service for display operations")
    else:
        # Ensure we use direct hardware access for testing
        os.environ['USE_EINK_SERVICE'] = '0'
        os.environ['EINK_TEST_MODE'] = '1'
        logger.info("Using direct hardware access for display operations")
    
    # Test the DisplayManager
    try:
        from managers.display_manager import DisplayManager
        
        # Create DisplayManager instance
        logger.info("Creating DisplayManager instance")
        
        # Specify driver if using software CS
        driver_name = None
        if args.use_sw_cs:
            driver_name = "waveshare_2in13_pi5_sw_cs"
            logger.info(f"Using software CS driver: {driver_name}")
            
        # Create the DisplayManager
        dm = DisplayManager(driver_name=driver_name)
        logger.info("DisplayManager created successfully")
        
        # Clear the screen
        logger.info("Clearing the screen")
        dm.clear_screen()
        logger.info("Screen cleared successfully")
        
        # Display test text
        logger.info("Displaying test text")
        dm.display_text("E-Ink Test", font_size=24)
        logger.info("Text displayed successfully")
        
        # Sleep the display
        logger.info("Putting the display to sleep")
        dm.sleep()
        logger.info("Display is now in sleep mode")
        
        # Wake the display
        logger.info("Waking up the display")
        dm.wake()
        logger.info("Display woken up successfully")
        
        # Display success message
        logger.info("Displaying success message")
        dm.display_text("Test Complete", font_size=24, y=40)
        logger.info("Success message displayed")
        
        return True
    except Exception as e:
        logger.error(f"Error during E-Ink display test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to run the system test"""
    # Configure logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Run the E-Ink test
    success = run_eink_test(args)
    
    # Display result
    if success:
        logger.info("System test completed successfully")
        return 0
    else:
        logger.error("System test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 