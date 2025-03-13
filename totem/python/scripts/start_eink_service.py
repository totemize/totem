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

def free_gpio_resources():
    """
    Free up GPIO resources by killing processes using them
    
    Returns:
        bool: Whether the operation was successful
    """
    try:
        # Check if any processes are using GPIO
        result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        
        if result.returncode != 0:
            logger.info("No processes found using GPIO")
            return True
            
        lines = result.stdout.strip().split('\n')
        if len(lines) <= 1:  # Just the header or empty
            logger.info("No processes found using GPIO")
            return True
            
        # Extract PIDs and command details
        processes = []
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 2:
                processes.append({
                    'pid': parts[1],
                    'command': parts[0]
                })
        
        if not processes:
            logger.info("No processes using GPIO")
            return True
        
        logger.info(f"Found {len(processes)} processes using GPIO:")
        for proc in processes:
            logger.info(f"  PID {proc['pid']} ({proc['command']})")
        
        # Ask for confirmation before killing
        if os.environ.get('EINK_FORCE_KILL_GPIO', '0') != '1':
            logger.warning("Automatic GPIO process termination is disabled. Set EINK_FORCE_KILL_GPIO=1 to enable.")
            return False
        
        # Kill each process
        for proc in processes:
            pid = proc['pid']
            logger.info(f"Killing process {pid}")
            subprocess.run(['kill', '-9', pid], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        
        # Wait a moment for processes to terminate
        time.sleep(1)
        
        # Check if they're gone
        result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        
        if result.returncode == 0 and len(result.stdout.strip().split('\n')) > 1:
            logger.warning("Some processes still using GPIO after kill attempt")
            return False
        
        logger.info("Successfully freed GPIO resources")
        return True
        
    except Exception as e:
        logger.error(f"Error freeing GPIO resources: {e}")
        return False

def is_service_running():
    """
    Check if the EInk service is already running
    
    Returns:
        tuple: (running, pid) - Whether service is running and its PID if found
    """
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
                    
                    # Find the process owning the socket
                    result = subprocess.run(['fuser', socket_path], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE, 
                                          text=True)
                    
                    if result.returncode == 0:
                        pids = result.stdout.strip().split()
                        if pids:
                            return True, pids[0]
                    
                    return True, None
                except:
                    logger.warning(f"Socket file exists but connection failed, it may be stale")
                    # Clean up stale socket file
                    try:
                        os.unlink(socket_path)
                        logger.info(f"Removed stale socket file: {socket_path}")
                    except Exception as e:
                        logger.error(f"Could not remove stale socket file: {e}")
        
        # Check for running process by name pattern
        try:
            result = subprocess.run(['pgrep', '-f', 'eink_service.py'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                if pids and pids[0]:
                    pid = pids[0]
                    logger.info(f"Found running EInk service process (PID: {pid})")
                    return True, pid
        except:
            pass
            
        # Alternative approach using ps and grep
        ps_cmd = "ps -ef | grep eink_service.py | grep -v grep"
        result = subprocess.run(ps_cmd, 
                              shell=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    logger.info(f"Found running EInk service process (PID: {pid})")
                    return True, pid
        
        logger.info("No running EInk service found")
        return False, None
    except Exception as e:
        logger.error(f"Error checking if service is running: {e}")
        return False, None

def wait_for_service_start(max_wait=10):
    """
    Wait for the service to start and verify it's running properly
    
    Args:
        max_wait: Maximum time to wait in seconds
        
    Returns:
        bool: Whether the service started successfully
    """
    logger.info(f"Waiting up to {max_wait} seconds for service to start...")
    
    # Wait for the socket file to appear and be connectable
    socket_path = os.environ.get('EINK_SOCKET_PATH', '/tmp/eink_service.sock')
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        # Check if the process is running
        running, _ = is_service_running()
        if running:
            # Verify socket works if using Unix sockets
            if os.environ.get('EINK_USE_TCP', '0') != '1':
                if os.path.exists(socket_path):
                    try:
                        import socket
                        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        sock.settimeout(1.0)
                        sock.connect(socket_path)
                        sock.close()
                        logger.info("Service started successfully and socket is responsive")
                        return True
                    except:
                        # Socket file exists but can't connect, keep waiting
                        pass
            else:
                # TCP mode, consider it running if the process is running
                return True
        
        # Wait before checking again
        time.sleep(1)
    
    logger.error(f"Service didn't start properly within {max_wait} seconds")
    return False

def start_service(driver_name=None, use_tcp=False, verbose=False, force_cleanup=False, mock_mode=False):
    """Start the EInk service as a daemon process"""
    # Check if already running
    running, pid = is_service_running()
    if running:
        logger.info("EInk service is already running")
        return True
    
    # Clean up any stale files
    socket_path = os.environ.get('EINK_SOCKET_PATH', '/tmp/eink_service.sock')
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
            logger.info(f"Removed stale socket file: {socket_path}")
        except Exception as e:
            logger.warning(f"Could not remove socket file: {e}")
    
    # If requested, free GPIO resources before starting
    if force_cleanup:
        logger.info("Attempting to free GPIO resources...")
        if not free_gpio_resources():
            logger.warning("Could not free all GPIO resources, continuing anyway")
    
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
    
    if force_cleanup:
        env['EINK_FORCE_KILL_GPIO'] = '1'
    
    if mock_mode:
        env['EINK_MOCK_MODE'] = '1'
    
    # Ensure the PYTHONPATH is correctly set
    if 'PYTHONPATH' not in env:
        env['PYTHONPATH'] = python_dir
    
    # Start the service as a background process
    try:
        log_file = '/tmp/eink_service.log'
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                [sys.executable, service_script],
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True  # Detach from parent process
            )
        
        logger.info(f"Started EInk service process (PID: {process.pid})")
        
        # Wait for the service to start
        if wait_for_service_start():
            logger.info("EInk service started successfully")
            return True
        else:
            # Service didn't start properly, check the log
            try:
                with open(log_file, 'r') as f:
                    log_content = f.read()
                    logger.error(f"Service startup log:\n{log_content}")
            except:
                pass
                
            logger.error("EInk service failed to start properly")
            
            # Try to kill the process
            try:
                os.kill(process.pid, signal.SIGTERM)
                logger.info(f"Terminated process {process.pid}")
            except:
                pass
                
            return False
    except Exception as e:
        logger.error(f"Error starting EInk service: {e}")
        return False

def stop_service(force=False):
    """Stop the running EInk service"""
    # Check if service is running
    running, pid = is_service_running()
    if not running:
        logger.info("No running EInk service found to stop")
        return True
    
    if not pid:
        logger.warning("Service is running but couldn't determine PID")
        if not force:
            return False
    
    try:
        if pid:
            # First try graceful shutdown with SIGTERM
            logger.info(f"Stopping EInk service process (PID: {pid})")
            os.kill(int(pid), signal.SIGTERM)
            
            # Wait for process to terminate
            max_wait = 5
            for i in range(max_wait):
                time.sleep(1)
                try:
                    # Check if process is still running
                    os.kill(int(pid), 0)  # This will raise an error if process doesn't exist
                    logger.info(f"Waiting for process to terminate ({i+1}/{max_wait})...")
                except OSError:
                    logger.info(f"Process {pid} terminated gracefully")
                    break
            else:
                # Process didn't terminate gracefully, use SIGKILL if forced
                if force:
                    logger.warning(f"Process did not terminate gracefully, sending SIGKILL")
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        logger.info(f"Sent SIGKILL to process {pid}")
                    except Exception as e:
                        logger.error(f"Error sending SIGKILL: {e}")
                else:
                    logger.warning(f"Process did not terminate gracefully and force option not enabled")
                    return False
        
        # Clean up socket file
        socket_path = os.environ.get('EINK_SOCKET_PATH', '/tmp/eink_service.sock')
        if os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
                logger.info(f"Removed socket file: {socket_path}")
            except Exception as e:
                logger.warning(f"Could not remove socket file: {e}")
        
        logger.info("EInk service stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping EInk service: {e}")
        if force:
            # Use more aggressive methods when force is enabled
            try:
                subprocess.run(['pkill', '-f', 'eink_service.py'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
                logger.info("Attempted to forcibly kill all EInk service processes")
                return True
            except:
                return False
        return False

def main():
    """Main function that parses command line arguments and runs the service"""
    parser = argparse.ArgumentParser(description="Start or stop the EInk service")
    
    # Action
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "cleanup"], 
                        help="Action to perform")
    
    # Driver option                        
    parser.add_argument("--driver", help="E-ink display driver to use")
    
    # Connection options
    parser.add_argument("--tcp", action="store_true", 
                        help="Use TCP instead of Unix socket for service communication")
    
    # Logging options
    parser.add_argument("--verbose", action="store_true", 
                        help="Enable verbose logging")
                        
    # Force options
    parser.add_argument("--force", action="store_true",
                        help="Force operations like killing processes")
                        
    # Mock mode
    parser.add_argument("--mock", action="store_true",
                        help="Run in mock mode (no hardware access)")
    
    args = parser.parse_args()
    
    if args.action == "status":
        # Check if the service is running
        running, pid = is_service_running()
        if running:
            status_msg = f"EInk service is running"
            if pid:
                status_msg += f" (PID: {pid})"
            print(status_msg)
            return 0
        else:
            print("EInk service is not running")
            return 1
    
    elif args.action == "stop":
        # Stop the service
        if stop_service(force=args.force):
            print("EInk service stopped successfully")
            return 0
        else:
            print("Failed to stop EInk service")
            return 1
    
    elif args.action == "restart":
        # Restart the service
        stop_service(force=args.force)
        time.sleep(1)  # Give it a moment to shut down completely
        if start_service(driver_name=args.driver, use_tcp=args.tcp, verbose=args.verbose, 
                        force_cleanup=args.force, mock_mode=args.mock):
            print("EInk service restarted successfully")
            return 0
        else:
            print("Failed to restart EInk service")
            return 1
    
    elif args.action == "start":
        # Start the service
        if start_service(driver_name=args.driver, use_tcp=args.tcp, verbose=args.verbose, 
                        force_cleanup=args.force, mock_mode=args.mock):
            print("EInk service started successfully")
            return 0
        else:
            print("Failed to start EInk service")
            return 1
            
    elif args.action == "cleanup":
        # Just clean up GPIO resources
        if free_gpio_resources():
            print("Successfully cleaned up GPIO resources")
            return 0
        else:
            print("Failed to clean up all GPIO resources")
            return 1

if __name__ == "__main__":
    sys.exit(main()) 