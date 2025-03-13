#!/usr/bin/env python3
"""
Service Display Image Example

This script demonstrates how to display an image file on the e-ink display
using the e-ink service. It uses the EInkClient to communicate with the service.

Usage:
    python3 service_display_image.py [/path/to/image.png]
    
If no image path is provided, it will use the default bitmap sample from the assets folder.

Run with:
    python3 service_display_image.py [/path/to/image.png]
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eink_service_image")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Display an image file on the e-ink display using the service')
    parser.add_argument('image_path', nargs='?', help='Path to the image file to display (optional)')
    args = parser.parse_args()
    
    # Add the project root to the Python path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    sys.path.insert(0, project_root)
    
    # If no image path is provided, use the default bitmap sample
    if args.image_path is None:
        default_image_path = os.path.join(project_root, "python", "assets", "bitmap-sample.bmp")
        if os.path.exists(default_image_path):
            args.image_path = default_image_path
            logger.info(f"Using default bitmap sample: {default_image_path}")
        else:
            logger.error("Default bitmap sample not found. Please provide an image path.")
            sys.exit(1)
    
    # Check if the image file exists
    if not os.path.exists(args.image_path):
        logger.error(f"Image file not found: {args.image_path}")
        sys.exit(1)
    
    try:
        # Import the EInkClient
        logger.info("Importing EInkClient...")
        from python.devices.eink.eink_client import EInkClient
        
        # Create the client
        logger.info("Creating EInkClient...")
        client = EInkClient()
        
        # Check if the service is running
        try:
            status = client.get_status()
            logger.info(f"E-ink service status: {status}")
        except Exception as e:
            logger.error(f"Error connecting to e-ink service: {e}")
            logger.error("Is the e-ink service running? You can start it with:")
            logger.error("  sudo poetry run eink-service")
            sys.exit(1)
        
        # Display the image file
        logger.info(f"Displaying image: {args.image_path}")
        response = client.display_image(image_path=args.image_path)
        logger.info(f"Service response: {response}")
        
        if response.get('status') == 'success':
            logger.info("Image displayed successfully!")
        else:
            logger.error(f"Failed to display image: {response.get('message', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 