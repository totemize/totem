#!/usr/bin/env python3
"""
E-Ink Service Stopper Script

This script stops the running e-ink display service.
It's designed to be called via poetry scripts.

Usage:
  poetry run eink-service-stop
"""

import os
import sys
import subprocess
import signal
import time

def stop_eink_service():
    """Stop the running e-ink service"""
    print("Stopping E-Ink service...")
    
    try:
        # First check if the service is running
        result = subprocess.run(
            ['pgrep', '-f', 'run_eink_service.py|eink_service.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            print("E-Ink service is not running")
            return True
        
        # Get the service PIDs
        pids = result.stdout.strip().split('\n')
        print(f"Found {len(pids)} running E-Ink service processes")
        
        # Terminate each process
        for pid in pids:
            pid = pid.strip()
            if not pid:
                continue
                
            print(f"Terminating PID: {pid}")
            try:
                subprocess.run(
                    ['sudo', 'kill', pid],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
            except subprocess.CalledProcessError:
                print(f"Failed to terminate PID {pid}, trying with SIGKILL")
                try:
                    subprocess.run(
                        ['sudo', 'kill', '-9', pid],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Failed to forcefully terminate PID {pid}: {e}")
        
        # Remove the socket file if it exists
        socket_path = '/tmp/eink_service.sock'
        if os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
                print(f"Removed socket file: {socket_path}")
            except Exception as e:
                print(f"Failed to remove socket file: {e}")
                # Try with sudo
                try:
                    subprocess.run(
                        ['sudo', 'rm', socket_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    print(f"Removed socket file with sudo: {socket_path}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to remove socket file with sudo: {e}")
        
        # Verify that the service is stopped
        time.sleep(1)
        result = subprocess.run(
            ['pgrep', '-f', 'run_eink_service.py|eink_service.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            print("Warning: Some processes may still be running")
            print("PIDs:", result.stdout.strip())
            return False
        
        print("E-Ink service stopped successfully")
        return True
    
    except Exception as e:
        print(f"Error stopping E-Ink service: {e}")
        return False

def main():
    """Main function"""
    success = stop_eink_service()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 