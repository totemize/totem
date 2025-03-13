#!/usr/bin/env python3
"""
Run E-Ink Service

This script starts the e-ink service and keeps it running in the foreground.
It ensures the service stays alive to handle Unix socket requests.

Usage:
    sudo python run_eink_service.py
"""

import os
import sys
import time
import signal
import argparse

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the service
from devices.eink.eink_service import EInkService

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) and SIGTERM signals"""
    print("\nReceived termination signal. Shutting down e-ink service...")
    if 'service' in globals():
        service.stop()
    sys.exit(0)

def main():
    """Start the e-ink service and keep it running"""
    parser = argparse.ArgumentParser(description='Run the E-Ink service')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without hardware')
    parser.add_argument('--socket-path', type=str, default='/tmp/eink_service.sock', 
                        help='Path to the Unix socket file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set environment variables
    if args.mock:
        os.environ['EINK_MOCK_MODE'] = '1'
    if args.debug:
        os.environ['LOGLEVEL'] = 'DEBUG'
        os.environ['EINK_DEBUG'] = '1'
    
    # Set socket path
    os.environ['EINK_SOCKET_PATH'] = args.socket_path
    os.environ['EINK_USE_TCP'] = '0'  # Force Unix socket mode
    
    # Set signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print(f"Starting E-Ink service (socket: {args.socket_path})...")
        
        # Create and start the service
        global service
        service = EInkService()
        
        # Start the service - this initializes the display and starts the socket server
        if not service.start():
            print("Failed to start the e-ink service properly")
            return
        
        print("E-Ink service started successfully. Ctrl+C to stop.")
        print(f"Unix socket: {args.socket_path}")
        
        # Keep the script running
        try:
            while not service.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Shutting down...")
        finally:
            service.stop()
            print("E-Ink service stopped.")
    
    except Exception as e:
        print(f"Error starting e-ink service: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Check if running as root (needed for GPIO access)
    if os.geteuid() != 0 and not ('EINK_MOCK_MODE' in os.environ and os.environ['EINK_MOCK_MODE'] == '1'):
        print("This script needs to be run as root to access GPIO pins.")
        print("Please run with: sudo python run_eink_service.py")
        sys.exit(1)
    
    main() 