#!/usr/bin/env python3
"""
Script to stop the EInk service
"""

import os
import sys
import argparse

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Import the start script which contains the service control functions
from scripts.start_eink_service import stop_service

def main():
    """Main function that parses command line arguments and stops the service"""
    parser = argparse.ArgumentParser(description="Stop the EInk service")
    
    # Force option for more aggressive shutdown
    parser.add_argument("--force", action="store_true", 
                      help="Force kill the service if it doesn't respond to gentle shutdown")
    
    args = parser.parse_args()
    
    # Stop the service
    if stop_service(force=args.force):
        print("EInk service stopped successfully")
        return 0
    else:
        print("Failed to stop EInk service")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 