#!/usr/bin/env python3
"""
Script to start the EInk service as a daemon process
"""

import os
import sys
import time
import argparse
import subprocess
import signal
import logging
from pathlib import Path

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
    logger = logging.getLogger("eink_service_starter")

def is_service_running():
    """Check if the EInk service is already running"""
    try:
        # First check the socket file
        if os.environ.get('EINK_USE_TCP', '0') != '1':
            socket_path = os.environ.get('EINK_SOCKET_PATH', '/tmp/eink_service.sock')
            if os.path.exists(socket_path):
                logger.info(f"Socket file {socket_path} exists")
                # Try to connect to confirm it's a valid socket
                import socket
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(1.0)
                    sock.connect(socket_path)
                    sock.close()
                    logger.info("Successfully connected to socket")
                    return True
                except:
                    logger.warning(f"Socket file exists but connection failed, it may be stale")
                    # Clean up stale socket file
                    try:
                        os.unlink(socket_path)
                    except:
                        pass
        
        # Check for running process
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'eink_service.py' in ' '.join(cmdline):
                logger.info(f"Found running EInk service process (PID: {proc.info['pid']})")
                return True
        
        logger.info("No running EInk service found")
        return False
    except Exception as e:
        logger.error(f"Error checking if service is running: {e}")
        return False

def start_service(driver_name=None, use_tcp=False, verbose=False):
    """Start the EInk service as a daemon process"""
    if is_service_running():
        logger.info("EInk service is already running")
        return
    
    # Get path to the service script
    service_script = str(Path(python_dir) / "devices" / "eink" / "eink_service.py")
    
    # Build environment variables
    env = os.environ.copy()
    
    if driver_name:
        env['EINK_DISPLAY_TYPE'] = driver_name
    
    if use_tcp:
        env['EINK_USE_TCP'] = '1'
    
    if verbose:
        env['LOGLEVEL'] = 'DEBUG'
    
    # Start the service as a background process
    try:
        with open('/tmp/eink_service.log', 'w') as f:
            subprocess.Popen(
                [sys.executable, service_script],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True  # Detach from parent process
            )
        
        logger.info("EInk service started in background")
        
        # Wait a moment for the service to start
        time.sleep(2)
        
        # Check if the service is running
        if is_service_running():
            logger.info("EInk service started successfully")
            return True
        else:
            logger.error("EInk service failed to start. Check the logs at /tmp/eink_service.log")
            return False
    except Exception as e:
        logger.error(f"Error starting EInk service: {e}")
        return False

def stop_service():
    """Stop the running EInk service"""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'eink_service.py' in ' '.join(cmdline):
                pid = proc.info['pid']
                logger.info(f"Stopping EInk service process (PID: {pid})")
                os.kill(pid, signal.SIGTERM)
                
                # Wait for process to terminate
                max_wait = 5
                for i in range(max_wait):
                    if not psutil.pid_exists(pid):
                        logger.info(f"EInk service process terminated successfully")
                        break
                    time.sleep(1)
                
                if psutil.pid_exists(pid):
                    logger.warning(f"Process did not terminate gracefully, sending SIGKILL")
                    os.kill(pid, signal.SIGKILL)
                
                return True
        
        logger.info("No running EInk service found to stop")
        return True
    except Exception as e:
        logger.error(f"Error stopping EInk service: {e}")
        return False

def main():
    """Main function that parses command line arguments and runs the service"""
    parser = argparse.ArgumentParser(description="Start or stop the EInk service")
    
    # Action
    parser.add_argument("action", choices=["start", "stop", "restart", "status"], 
                        help="Action to perform")
    
    # Driver option                        
    parser.add_argument("--driver", help="E-ink display driver to use")
    
    # Connection options
    parser.add_argument("--tcp", action="store_true", 
                        help="Use TCP instead of Unix socket for service communication")
    
    # Logging options
    parser.add_argument("--verbose", action="store_true", 
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.action == "status":
        # Check if the service is running
        if is_service_running():
            print("EInk service is running")
            return 0
        else:
            print("EInk service is not running")
            return 1
    
    elif args.action == "stop":
        # Stop the service
        if stop_service():
            print("EInk service stopped successfully")
            return 0
        else:
            print("Failed to stop EInk service")
            return 1
    
    elif args.action == "restart":
        # Restart the service
        stop_service()
        time.sleep(1)  # Give it a moment to shut down completely
        if start_service(driver_name=args.driver, use_tcp=args.tcp, verbose=args.verbose):
            print("EInk service restarted successfully")
            return 0
        else:
            print("Failed to restart EInk service")
            return 1
    
    elif args.action == "start":
        # Start the service
        if start_service(driver_name=args.driver, use_tcp=args.tcp, verbose=args.verbose):
            print("EInk service started successfully")
            return 0
        else:
            print("Failed to start EInk service")
            return 1

if __name__ == "__main__":
    sys.exit(main()) 