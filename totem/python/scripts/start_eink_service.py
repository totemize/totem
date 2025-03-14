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

# Define log file path
LOG_FILE_PATH = '/tmp/totem-eink-service.log'

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
    parser.add_argument('--log-file', type=str, default=LOG_FILE_PATH,
                      help='Path to the log file')
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
    print(f"Logging output to: {args.log_file}")
    
    try:
        # Make sure the log directory exists
        log_dir = os.path.dirname(args.log_file)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            print(f"Created log directory: {log_dir}")
        
        # Open the log file
        with open(args.log_file, 'a') as log_file:
            # Write a startup marker to the log
            log_file.write(f"\n\n{'='*80}\n")
            log_file.write(f"Starting E-Ink service at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"Command: {' '.join(cmd)}\n")
            log_file.write(f"{'='*80}\n\n")
            log_file.flush()
            
            # Start the process with stdout and stderr redirected to the log file
            # Use subprocess.DEVNULL for stdin to fully detach from terminal
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True  # This creates a new process group
            )
            
            # Wait a bit for the service to start
            time.sleep(3)
            
            # Check if the process is still running
            if process.poll() is None:
                print(f"E-Ink service started successfully with PID {process.pid}")
                print(f"Socket path: {args.socket_path}")
                print(f"Log file: {args.log_file}")
                print("The service is running in the background.")
                print("To stop it, run: sudo pkill -f 'run_eink_service.py|eink_service.py'")
                print(f"To view logs: tail -f {args.log_file}")
                
                # We don't need to call os.setpgrp() here since we used start_new_session=True
            else:
                stdout, _ = process.communicate()
                print(f"Service failed to start. Exit code: {process.returncode}")
                print(f"Check the log file for details: {args.log_file}")
                return 1
        
        # Reset terminal to fix any display issues
        # This sends a terminal reset sequence
        print("\033[0m", end="", flush=True)  # Reset all attributes
        
        return 0
    except KeyboardInterrupt:
        print("\nStartup interrupted by user")
        # Reset terminal
        print("\033[0m", end="", flush=True)
        return 0
    except Exception as e:
        print(f"Error starting service: {e}")
        # Reset terminal
        print("\033[0m", end="", flush=True)
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        # Final terminal reset before exiting
        print("\033[0m", end="", flush=True)
        sys.exit(exit_code)
    except Exception as e:
        print(f"Unexpected error: {e}")
        # Reset terminal
        print("\033[0m", end="", flush=True)
        sys.exit(1) 