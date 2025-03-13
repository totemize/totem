#!/usr/bin/env python3
"""
Test script for the EInk service
This script tests both the service mode and direct hardware access mode
"""

import os
import sys
import time
import argparse
import traceback
import logging
import subprocess
import json
import socket

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

try:
    from utils.logger import logger
except ImportError:
    # Create a logger if the main logger is not available
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    logger = logging.getLogger("eink_service_test")

# Import the display manager
try:
    from managers.display_manager import DisplayManager
except ImportError:
    logger.error("Could not import DisplayManager. Make sure you're in the correct directory.")
    sys.exit(1)

# Import service scripts
try:
    from scripts.start_eink_service import start_service, stop_service, free_gpio_resources
    from devices.eink.eink_client import EInkClient
except ImportError:
    logger.error("Could not import service scripts. Make sure you're in the correct directory.")
    sys.exit(1)


def test_direct_mode(display_type=None, retry_count=3, verbose=False):
    """
    Test the display manager in direct hardware access mode
    
    Args:
        display_type: Type of display to use
        retry_count: Number of retries if failed
        verbose: Whether to enable verbose logging
    
    Returns:
        bool: Success or failure
    """
    logger.info("Testing DisplayManager in direct hardware access mode")
    
    # Set environment variables
    os.environ['USE_EINK_SERVICE'] = '0'
    
    if display_type:
        os.environ['EINK_DISPLAY_TYPE'] = display_type
    
    if verbose:
        os.environ['LOGLEVEL'] = 'DEBUG'
    
    # Initialize display manager with retries
    for attempt in range(retry_count):
        try:
            logger.info(f"Initializing DisplayManager (attempt {attempt+1}/{retry_count})")
            
            # Create DisplayManager
            dm = DisplayManager()
            
            # Test basic operations
            logger.info("Clearing screen")
            dm.clear_screen()
            
            logger.info("Displaying text")
            dm.display_text("EInk Test\nDirect Mode", font_size=24)
            
            logger.info("Test completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error in direct mode test (attempt {attempt+1}): {e}")
            logger.error(traceback.format_exc())
            
            if attempt < retry_count - 1:
                # Clean up resources before retry
                try:
                    if 'dm' in locals():
                        del dm
                except:
                    pass
                
                # Try to free GPIO resources
                logger.info("Attempting to free GPIO resources before retry")
                free_gpio_resources()
                
                # Wait before retry
                logger.info(f"Waiting 2 seconds before retry...")
                time.sleep(2)
    
    logger.error(f"Direct mode test failed after {retry_count} attempts")
    return False


def test_service_mode(display_type=None, retry_count=3, verbose=False, mock_mode=False):
    """
    Test the display manager in service mode
    
    Args:
        display_type: Type of display to use
        retry_count: Number of retries if failed
        verbose: Whether to enable verbose logging
        mock_mode: Whether to use mock mode
    
    Returns:
        bool: Success or failure
    """
    logger.info("Testing DisplayManager in service mode")
    
    # Stop any existing service
    logger.info("Stopping any existing EInk service")
    stop_service(force=True)
    time.sleep(1)
    
    # Start the service
    logger.info("Starting EInk service")
    if not start_service(
        driver_name=display_type, 
        verbose=verbose, 
        force_cleanup=True,
        mock_mode=mock_mode
    ):
        logger.error("Failed to start EInk service")
        return False
    
    # Wait for service to be fully operational
    logger.info("Waiting for service to be ready")
    time.sleep(3)
    
    # Set environment variables for DisplayManager
    os.environ['USE_EINK_SERVICE'] = '1'
    
    if display_type:
        os.environ['EINK_DISPLAY_TYPE'] = display_type
    
    if verbose:
        os.environ['LOGLEVEL'] = 'DEBUG'
    
    # Test using the client directly
    success = False
    for attempt in range(retry_count):
        try:
            logger.info(f"Testing EInk client (attempt {attempt+1}/{retry_count})")
            
            # Create client
            client = EInkClient()
            
            # Test basic operations
            logger.info("Clearing screen via client")
            result = client.clear_screen()
            logger.info(f"Clear screen result: {result}")
            
            logger.info("Displaying text via client")
            result = client.display_text(
                "EInk Test\nService Mode", 
                x=10, y=10, 
                font_size=24
            )
            logger.info(f"Display text result: {result}")
            
            # Get status
            logger.info("Getting service status")
            result = client.get_status()
            logger.info(f"Service status: {result}")
            
            logger.info("Client test completed successfully!")
            success = True
            break
            
        except Exception as e:
            logger.error(f"Error in service mode client test (attempt {attempt+1}): {e}")
            logger.error(traceback.format_exc())
            
            if attempt < retry_count - 1:
                # Wait before retry
                logger.info(f"Waiting 2 seconds before retry...")
                time.sleep(2)
    
    # Now test using DisplayManager with service mode
    if success:
        try:
            logger.info("Testing DisplayManager with service mode")
            
            # Create DisplayManager
            dm = DisplayManager()
            
            # Test basic operations
            logger.info("Clearing screen via DisplayManager")
            dm.clear_screen()
            
            logger.info("Displaying text via DisplayManager")
            dm.display_text("EInk Test\nService Mode\nvia DisplayManager", font_size=20)
            
            logger.info("DisplayManager test completed successfully!")
            
        except Exception as e:
            logger.error(f"Error in DisplayManager service mode test: {e}")
            logger.error(traceback.format_exc())
            success = False
    
    # Stop the service
    logger.info("Stopping EInk service")
    stop_service(force=True)
    
    if not success:
        logger.error("Service mode test failed")
    
    return success


def main():
    """Main function for the test script"""
    parser = argparse.ArgumentParser(description="Test the EInk display functionality")
    
    # Mode selection
    parser.add_argument("--mode", choices=["direct", "service", "both"], default="both",
                      help="Test mode: direct hardware access, service mode, or both")
    
    # Display type
    parser.add_argument("--display", help="E-ink display type to use")
    
    # Mock mode
    parser.add_argument("--mock", action="store_true",
                      help="Use mock mode (no hardware access)")
    
    # Verbosity
    parser.add_argument("--verbose", action="store_true",
                      help="Enable verbose logging")
    
    # Retry count
    parser.add_argument("--retries", type=int, default=3,
                      help="Number of retries for each test")
    
    args = parser.parse_args()
    
    # Run the tests
    direct_result = True
    service_result = True
    
    if args.mode in ["direct", "both"]:
        logger.info("=== TESTING DIRECT HARDWARE ACCESS MODE ===")
        direct_result = test_direct_mode(
            display_type=args.display,
            retry_count=args.retries,
            verbose=args.verbose
        )
        logger.info(f"Direct mode test {'PASSED' if direct_result else 'FAILED'}")
    
    if args.mode in ["service", "both"]:
        logger.info("=== TESTING SERVICE MODE ===")
        service_result = test_service_mode(
            display_type=args.display,
            retry_count=args.retries,
            verbose=args.verbose,
            mock_mode=args.mock
        )
        logger.info(f"Service mode test {'PASSED' if service_result else 'FAILED'}")
    
    # Overall result
    if args.mode == "both":
        if direct_result and service_result:
            logger.info("All tests PASSED!")
            return 0
        else:
            logger.error("Some tests FAILED")
            return 1
    elif args.mode == "direct":
        if direct_result:
            logger.info("Direct mode test PASSED!")
            return 0
        else:
            logger.error("Direct mode test FAILED")
            return 1
    elif args.mode == "service":
        if service_result:
            logger.info("Service mode test PASSED!")
            return 0
        else:
            logger.error("Service mode test FAILED")
            return 1


if __name__ == "__main__":
    sys.exit(main()) 