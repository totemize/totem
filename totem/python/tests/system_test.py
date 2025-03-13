import argparse
import logging
import os
import sys
import time
import importlib.util

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Configure the logger
from utils.logger import logger

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run system tests for E-Ink display')
parser.add_argument('--mock', action='store_true', help='Use mock mode (no hardware)')
parser.add_argument('--nvme', action='store_true', help='Use NVME compatibility mode')
parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
parser.add_argument('--quick', action='store_true', help='Run quick GPIO test only')
parser.add_argument('--pi5', action='store_true', help='Run specific test for Raspberry Pi 5')
parser.add_argument('--simple', action='store_true', help='Run simple test without PIL')
parser.add_argument('--manufacturer', action='store_true', help='Run test emulating manufacturer approach')
parser.add_argument('--all', action='store_true', help='Run all tests')
args = parser.parse_args()

def import_test_module(module_name):
    """Import a test module dynamically"""
    try:
        # Check if the module exists in the eink subdirectory first
        module_path = os.path.join(script_dir, "eink", f"{module_name}.py")
        if not os.path.exists(module_path):
            # If not found in eink subdirectory, check in the main directory
            module_path = os.path.join(script_dir, f"{module_name}.py")
            if not os.path.exists(module_path):
                logger.error(f"Test module '{module_name}.py' not found in tests or tests/eink directory")
                return None
            
        # Import the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        logger.error(f"Error importing test module '{module_name}': {e}")
        return None

def run_quick_test():
    """Run the quick GPIO test"""
    logger.info("Running quick GPIO test")
    try:
        module = import_test_module("eink_quick_test")
        if module:
            return module.main() == 0
        return False
    except Exception as e:
        logger.error(f"Error running quick test: {e}")
        return False

def run_pi5_test():
    """Run the Raspberry Pi 5 specific test"""
    logger.info("Running Raspberry Pi 5 specific test")
    try:
        module = import_test_module("test_pi5_eink")
        if module:
            module.main()
            return True
        return False
    except Exception as e:
        logger.error(f"Error running Pi 5 test: {e}")
        return False

def run_simple_test():
    """Run the simple E-ink test without PIL"""
    logger.info("Running simple E-ink test")
    try:
        module = import_test_module("eink_simple_test")
        if module:
            args_dict = {
                'mock': args.mock,
                'nvme': args.nvme,
                'verbose': args.verbose
            }
            # Create argparse.Namespace object from dictionary
            module_args = argparse.Namespace(**args_dict)
            
            # Check if the module has a proper main function
            if hasattr(module, 'main'):
                return module.main() == 0
            return False
        return False
    except Exception as e:
        logger.error(f"Error running simple test: {e}")
        return False

def run_manufacturer_test():
    """Run the test emulating the manufacturer approach"""
    logger.info("Running manufacturer-style test")
    try:
        module = import_test_module("eink_emulate_manufacturer")
        if module:
            return module.run_test(
                nvme_compatible=args.nvme,
                mock_mode=args.mock,
                busy_timeout=10
            )
        return False
    except Exception as e:
        logger.error(f"Error running manufacturer test: {e}")
        return False

def run_diagnostics():
    """Run E-ink diagnostics"""
    logger.info("Running E-ink diagnostics")
    try:
        # Import the module without running main()
        module = import_test_module("test_eink_diagnostics")
        if module:
            # Only run the GPIO pins test which is non-invasive
            if hasattr(module, 'test_gpio_pins'):
                logger.info("Running GPIO pin diagnostics")
                success = module.test_gpio_pins()
                return success
            else:
                logger.warning("test_eink_diagnostics.py doesn't have test_gpio_pins function")
                return False
        return False
    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return False

def main():
    """Main function to run system tests"""
    # Configure logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    results = {}
    success = True
    
    # Run diagnostic check first
    logger.info("Starting diagnostics check...")
    diag_success = run_diagnostics()
    results["Diagnostics"] = "PASSED" if diag_success else "FAILED"
    
    # Run the appropriate tests based on arguments
    if args.all:
        # Run all tests
        if run_quick_test():
            results["Quick GPIO Test"] = "PASSED"
        else:
            results["Quick GPIO Test"] = "FAILED"
            success = False
            
        if run_simple_test():
            results["Simple E-ink Test"] = "PASSED"
        else:
            results["Simple E-ink Test"] = "FAILED"
            success = False
            
        if run_manufacturer_test():
            results["Manufacturer-style Test"] = "PASSED"
        else:
            results["Manufacturer-style Test"] = "FAILED"
            success = False
            
        # Only run Pi5 test if on a Pi 5
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                if 'Raspberry Pi 5' in model:
                    if run_pi5_test():
                        results["Pi 5 Test"] = "PASSED"
                    else:
                        results["Pi 5 Test"] = "FAILED"
                        success = False
    elif args.quick:
        # Run just the quick test
        success = run_quick_test()
        results["Quick GPIO Test"] = "PASSED" if success else "FAILED"
    elif args.pi5:
        # Run just the Pi 5 test
        success = run_pi5_test()
        results["Pi 5 Test"] = "PASSED" if success else "FAILED"
    elif args.simple:
        # Run just the simple test
        success = run_simple_test()
        results["Simple E-ink Test"] = "PASSED" if success else "FAILED"
    elif args.manufacturer:
        # Run just the manufacturer test
        success = run_manufacturer_test()
        results["Manufacturer-style Test"] = "PASSED" if success else "FAILED"
    else:
        # Default: run simple test or manufacturer test based on availability of PIL
        try:
            from PIL import Image
            # PIL is available, use manufacturer test
            success = run_manufacturer_test()
            results["Manufacturer-style Test"] = "PASSED" if success else "FAILED"
        except ImportError:
            # PIL not available, use simple test
            success = run_simple_test()
            results["Simple E-ink Test"] = "PASSED" if success else "FAILED"
    
    # Print results
    logger.info("=== Test Results ===")
    for test, result in results.items():
        logger.info(f"{test}: {result}")
    
    if success:
        logger.info("System test completed successfully")
        return 0
    else:
        logger.error("System test failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 