#!/usr/bin/env python3
"""
E-Ink Service Launcher Script

This script starts the e-ink display service as a background process.
It's designed to be called via poetry scripts.

Usage:
  poetry run eink-service
  poetry run eink-service --verbose
  poetry run eink-service --mock
"""

import os
import sys
import argparse
import subprocess
import signal
import time
from pathlib import Path

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Check if the service file exists
SERVICE_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../examples/run_eink_service.py'))
if not os.path.exists(SERVICE_SCRIPT):
    SERVICE_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../devices/eink/eink_service.py'))

def check_if_service_running():
    """Check if the e-ink service is already running"""
    try:
        # Try to check if there's an existing service process
        result = subprocess.run(
            ['pgrep', '-f', 'run_eink_service.py|eink_service.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        return False, None
    except Exception as e:
        print(f"Error checking for existing service: {e}")
        return False, None

def main():
    """Main function to start the e-ink service"""
    parser = argparse.ArgumentParser(description='Start the E-Ink Service')
    parser.add_argument('--mock', action='store_true', help='Run in mock mode without hardware')
    parser.add_argument('--socket-path', type=str, default='/tmp/eink_service.sock',
                      help='Path to the Unix socket file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Check if service is already running
    running, pid = check_if_service_running()
    if running:
        print(f"E-Ink service is already running (PID: {pid})")
        print("To restart, stop the existing service first with: sudo pkill -f 'run_eink_service.py|eink_service.py'")
        return 0
    
    # Build the command
    cmd = ['sudo', 'python3', SERVICE_SCRIPT]
    
    if args.mock:
        cmd.append('--mock')
    if args.debug:
        cmd.append('--debug')
    if args.verbose:
        cmd.append('--verbose')
    if args.socket_path:
        cmd.extend(['--socket-path', args.socket_path])
    
    # Output status
    print(f"Starting E-Ink service...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Wait a bit for the service to start
        time.sleep(3)
        
        # Check if the process is still running
        if process.poll() is None:
            print(f"E-Ink service started successfully with PID {process.pid}")
            print(f"Socket path: {args.socket_path}")
            print("The service is running in the background.")
            print("To stop it, run: sudo pkill -f 'run_eink_service.py|eink_service.py'")
            
            # Detach the process (doesn't work fully in Python, but helps)
            process.stdout.close()
            os.setpgrp()
        else:
            stdout, _ = process.communicate()
            print(f"Service failed to start. Exit code: {process.returncode}")
            print("Output:")
            print(stdout)
            return 1
        
        return 0
    except KeyboardInterrupt:
        print("\nStartup interrupted by user")
        return 0
    except Exception as e:
        print(f"Error starting service: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 