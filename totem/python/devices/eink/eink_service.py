#!/usr/bin/env python3
"""
EInk Service - Persistent process to manage e-ink display hardware

This service maintains exclusive access to the GPIO pins used by the e-ink display
and provides a socket-based API for other processes to send display commands.
"""

import os
import sys
import time
import json
import socket
import signal
import threading
import queue
import base64
import traceback
from pathlib import Path
import logging
import subprocess
import select
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional, List, Tuple, Union
import errno

# Add the parent directory to path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
devices_dir = os.path.dirname(os.path.dirname(script_dir))
python_dir = os.path.dirname(devices_dir)
sys.path.insert(0, python_dir)

try:
    from utils.logger import logger
except ImportError:
    # Create a logger if the main logger is not available
    logging.basicConfig(
        level=logging.INFO if os.environ.get('LOGLEVEL', 'INFO') != 'DEBUG' else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.expanduser('~/eink_service.log'))
        ]
    )
    logger = logging.getLogger("eink_service")

# Try to import the proper EInk driver classes
try:
    # First try to import from direct module path
    from devices.eink.waveshare_3in7 import WaveshareEPD3in7
    from devices.eink.mock_epd import MockEPD
    logger.info("Successfully imported direct device drivers")
except ImportError:
    try:
        # Try to import from drivers subdirectory
        from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
        from devices.eink.drivers.mock_epd import MockEPD
        logger.info("Successfully imported device drivers from drivers subdirectory")
    except ImportError:
        # As a last resort, try importing from current directory
        try:
            from waveshare_3in7 import WaveshareEPD3in7
            from mock_epd import MockEPD
            logger.info("Successfully imported device drivers from current directory")
        except ImportError:
            logger.error("Failed to import device drivers")
            # Create placeholder classes to avoid errors
            class MockEPD:
                def __init__(self):
                    pass
                def init(self):
                    pass
                def Clear(self):
                    pass
                def close(self):
                    pass
                def cleanup(self):
                    pass
                def sleep(self):
                    pass
                def display_text(self, text, x=10, y=10, font_size=24):
                    pass
            
            class WaveshareEPD3in7(MockEPD):
                pass

# Try to import EInk class for higher-level abstraction
try:
    from devices.eink.eink import EInk
    logger.info("Successfully imported EInk class")
    HAS_EINK_CLASS = True
except ImportError:
    logger.warning("Could not import EInk class, using direct driver access")
    HAS_EINK_CLASS = False

# Constants
DEFAULT_SOCKET_PATH = "/tmp/eink_service.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 8797
INACTIVITY_TIMEOUT = 300  # 5 minutes
MAX_RETRIES = 3  # Maximum number of retries for initialization
MAX_MSG_SIZE = 65536
RETRY_DELAY = 2  # seconds


class EInkService:
    """
    Service that maintains exclusive access to the e-ink display and
    provides a socket-based interface for display operations.
    """
    
    def __init__(self):
        """
        Initialize the EInk service
        """
        logger.info("Initializing EInk Service")
        self.stop_event = threading.Event()
        self.display = None
        self.eink = None  # Add this for backward compatibility with old code
        self.socket_server = None
        self.clients = []
        self.command_queue = []
        self.use_tcp = os.environ.get('EINK_USE_TCP', '0') == '1'
        self.socket_path = os.environ.get('EINK_SOCKET_PATH', DEFAULT_SOCKET_PATH)
        self.tcp_port = int(os.environ.get('EINK_TCP_PORT', DEFAULT_TCP_PORT))
        self.tcp_host = os.environ.get('EINK_TCP_HOST', 'localhost')
        self.lock = threading.RLock()
        self.initialized = False
        self.mock_mode = os.environ.get('EINK_MOCK_MODE', '0') == '1'
        self.force_kill_gpio = os.environ.get('EINK_FORCE_KILL_GPIO', '0') == '1'
        self.init_retries = 0
        self.max_init_retries = int(os.environ.get('EINK_MAX_INIT_RETRIES', MAX_RETRIES))
        # Add a flag to track if the socket server is ready
        self.socket_server_ready = threading.Event()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("EInk Service initialized successfully")
    
    def _check_gpio_availability(self) -> Tuple[bool, str]:
        """
        Check if GPIO pins are available and not in use by other processes
        
        Returns:
            Tuple of (available, message)
        """
        try:
            # Check if any processes are using GPIO
            result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
            
            if result.returncode != 0:
                return True, "No processes found using GPIO"
                
            lines = result.stdout.strip().split('\n')
            if len(lines) <= 1:  # Just the header or empty
                return True, "No processes found using GPIO"
                
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
                return True, "No processes using GPIO"
            
            message = f"Found {len(processes)} processes using GPIO:"
            for proc in processes:
                message += f"\n  PID {proc['pid']} ({proc['command']})"
            
            return False, message
            
        except Exception as e:
            logger.error(f"Error checking GPIO availability: {e}")
            return False, f"Error checking GPIO: {str(e)}"
    
    def _kill_gpio_processes(self) -> Tuple[bool, str]:
        """
        Attempt to kill processes using GPIO
        
        Returns:
            Tuple of (success, message)
        """
        if not self.force_kill_gpio:
            return False, "GPIO process termination not enabled (set EINK_FORCE_KILL_GPIO=1 to enable)"
        
        try:
            # Check if any processes are using GPIO
            result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
            
            if result.returncode != 0:
                return True, "No processes found using GPIO"
                
            lines = result.stdout.strip().split('\n')
            if len(lines) <= 1:  # Just the header or empty
                return True, "No processes found using GPIO"
                
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
                return True, "No processes using GPIO"
            
            # Kill each process
            killed_pids = []
            for proc in processes:
                pid = proc['pid']
                logger.info(f"Killing process {pid}")
                subprocess.run(['kill', '-9', pid], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
                killed_pids.append(pid)
            
            # Wait a moment for processes to terminate
            time.sleep(1)
            
            # Check if they're gone
            result = subprocess.run(['lsof', '/dev/gpiochip0'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True)
            
            if result.returncode == 0 and len(result.stdout.strip().split('\n')) > 1:
                return False, "Some processes still using GPIO after kill attempt"
            
            return True, f"Successfully killed processes: {', '.join(killed_pids)}"
            
        except Exception as e:
            logger.error(f"Error killing GPIO processes: {e}")
            return False, f"Error killing GPIO processes: {str(e)}"
    
    def start(self):
        """Initialize and start the EInk service"""
        logger.info("Starting EInk service...")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            # Check if GPIO is available
            gpio_available, message = self._check_gpio_availability()
            logger.info(f"GPIO availability check: {message}")
            
            if not gpio_available and self.force_kill_gpio:
                # Try to kill processes using GPIO
                kill_success, kill_message = self._kill_gpio_processes()
                logger.info(f"GPIO process cleanup: {kill_message}")
                
                # Check again after killing
                gpio_available, message = self._check_gpio_availability()
                logger.info(f"GPIO availability after cleanup: {message}")
            
            # Initialize display (with retry mechanism)
            if not self._initialize_display():
                logger.error("Failed to initialize display after retries, using mock mode")
                self.mock_mode = True
                if not self._initialize_display():  # Try once more with mock mode
                    logger.error("Failed to initialize display even in mock mode")
                    return False
            
            # Backward compatibility: If there's a reference to self.eink, set it up
            if hasattr(self, 'eink') and self.eink is None and self.display is not None:
                logger.info("Setting up backward compatibility for eink attribute")
                class EinkWrapper:
                    def __init__(self, display):
                        self.driver = display
                    
                    def initialize(self):
                        if hasattr(self.driver, 'init'):
                            return self.driver.init()
                        return None
                        
                self.eink = EinkWrapper(self.display)
            
            # Mark as initialized
            self.initialized = True
            logger.info("Display initialized successfully")
            
            # Start socket server
            logger.info("Setting up socket server...")
            socket_setup_success = self._setup_socket_server()
            if not socket_setup_success:
                logger.error("Failed to set up socket server, service will not be able to receive commands")
                return False
            
            # Wait for socket server to be ready (with timeout)
            logger.info("Waiting for socket server to be ready...")
            if not self.socket_server_ready.wait(timeout=5.0):
                logger.error("Timed out waiting for socket server to be ready")
                return False
                
            logger.info("Socket server is ready, starting command processing loop...")
            
            # Start command processing loop
            self._process_commands()
            
        except Exception as e:
            logger.error(f"Error starting EInk service: {e}")
            logger.error(traceback.format_exc())
            
            # Clean up resources as best we can
            self.cleanup()
            return False
            
        return True
    
    def stop(self):
        """Stop the EInk service and clean up resources"""
        if not self.initialized:
            logger.warning("EInk Service is not running")
            return
            
        logger.info("Stopping EInk Service")
        self.stop_event.set()
        
        # Wait for threads to finish
        if hasattr(self, 'server_thread') and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
            
        # Clean up display resources - try both self.display and self.eink for compatibility
        # First try with self.display
        if hasattr(self, 'display') and self.display is not None:
            try:
                # Put display to sleep
                logger.info("Putting display to sleep before shutdown")
                if hasattr(self.display, 'sleep'):
                    self.display.sleep()
                
                # Perform cleanup
                logger.info("Cleaning up hardware resources (display)")
                if hasattr(self.display, 'cleanup'):
                    self.display.cleanup()
                elif hasattr(self.display, 'close'):
                    self.display.close()
            except Exception as e:
                logger.error(f"Error during display cleanup: {e}")
            self.display = None
        
        # Then try with self.eink for backward compatibility
        if hasattr(self, 'eink') and self.eink is not None:
            try:
                logger.info("Cleaning up hardware resources (eink)")
                if hasattr(self.eink, 'driver'):
                    driver = self.eink.driver
                    if hasattr(driver, 'sleep'):
                        logger.info("Putting eink driver to sleep")
                        driver.sleep()
                    if hasattr(driver, 'cleanup'):
                        logger.info("Cleaning up eink driver")
                        driver.cleanup()
                    elif hasattr(driver, 'close'):
                        logger.info("Closing eink driver")
                        driver.close()
            except Exception as e:
                logger.error(f"Error during eink driver cleanup: {e}")
            self.eink = None
            
        # Remove socket file if using Unix sockets
        if not self.use_tcp and hasattr(self, 'socket_path') and os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
                logger.info(f"Removed socket file: {self.socket_path}")
            except Exception as e:
                logger.error(f"Error removing socket file: {e}")
            
        logger.info("EInk Service stopped")
    
    def signal_handler(self, sig, frame):
        """Handle termination signals for graceful shutdown"""
        logger.info(f"Received signal {sig}, shutting down")
        self.stop()
    
    def run_unix_socket_server(self):
        """Run a Unix domain socket server for local communication"""
        logger.info(f"Starting Unix socket server at {self.socket_path}")
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
                logger.info(f"Removed existing socket file: {self.socket_path}")
            except Exception as e:
                logger.error(f"Error removing existing socket file: {e}")
                # Continue anyway and attempt to bind
        
        # Create socket server
        try:
            self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket_server.bind(self.socket_path)
            self.socket_server.listen(5)
            self.socket_server.settimeout(1.0)  # Allow checking running flag
            
            # Ensure socket file has the right permissions
            try:
                os.chmod(self.socket_path, 0o666)  # Allow anyone to read/write
                logger.info(f"Set socket file permissions to 0o666")
                # Add debug logging to verify socket file exists
                if os.path.exists(self.socket_path):
                    logger.info(f"Socket file created successfully at {self.socket_path}")
                else:
                    logger.error(f"Socket file not found at {self.socket_path} even though binding succeeded")
            except Exception as e:
                logger.warning(f"Could not set socket file permissions: {e}")
            
            logger.info("Unix socket server ready")
            
            # Signal that the socket server is ready
            self.socket_server_ready.set()
            
            while self.initialized:
                try:
                    client, _ = self.socket_server.accept()
                    self._handle_client(client)
                except socket.timeout:
                    # This just allows us to check the running flag
                    continue
                except Exception as e:
                    if self.initialized:  # Only log if we're not in shutdown
                        logger.error(f"Socket server error: {e}")
                        logger.error(traceback.format_exc())
            
            # Clean up
            self.socket_server.close()
            logger.info("Unix socket server stopped")
        except Exception as e:
            logger.error(f"Error setting up Unix socket server: {e}")
            logger.error(traceback.format_exc())
            self.initialized = False
    
    def run_tcp_server(self):
        """Run a TCP server for network communication"""
        logger.info(f"Starting TCP server at {self.tcp_host}:{self.tcp_port}")
        
        try:
            # Create socket server
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind((self.tcp_host, self.tcp_port))
            self.socket_server.listen(5)
            self.socket_server.settimeout(1.0)  # Allow checking running flag
            
            logger.info("TCP server ready")
            
            # Signal that the socket server is ready
            self.socket_server_ready.set()
            
            while self.initialized:
                try:
                    client, addr = self.socket_server.accept()
                    logger.debug(f"Connection from {addr}")
                    self._handle_client(client)
                except socket.timeout:
                    # This just allows us to check the running flag
                    continue
                except Exception as e:
                    if self.initialized:  # Only log if we're not in shutdown
                        logger.error(f"Socket server error: {e}")
                        logger.error(traceback.format_exc())
            
            # Clean up
            self.socket_server.close()
            logger.info("TCP server stopped")
        except Exception as e:
            logger.error(f"Error setting up TCP server: {e}")
            logger.error(traceback.format_exc())
            self.initialized = False
    
    def _handle_client(self, client):
        """Handle a client connection and process their command"""
        try:
            # Set a timeout for receiving data
            client.settimeout(5.0)
            
            # Read data from client
            data = b""
            while True:
                chunk = client.recv(MAX_MSG_SIZE)
                if not chunk:
                    break
                data += chunk
                
                # Check if we have a complete JSON object
                try:
                    _ = json.loads(data.decode('utf-8'))
                    break  # We have a complete JSON object
                except:
                    pass  # Continue reading
            
            if not data:
                return
                
            # Parse command
            try:
                command = json.loads(data.decode('utf-8'))
                logger.debug(f"Received command: {command}")
                
                # Queue the command for processing
                self.command_queue.append((client, command))
                
                # Send acknowledgement
                response = {"status": "queued", "message": "Command accepted"}
                client.send(json.dumps(response).encode('utf-8'))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON data: {data.decode('utf-8')}")
                response = {"status": "error", "message": "Invalid JSON data"}
                client.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling client: {e}")
            try:
                response = {"status": "error", "message": str(e)}
                client.send(json.dumps(response).encode('utf-8'))
            except:
                pass
        finally:
            client.close()
    
    def _setup_socket_server(self):
        """Set up the socket server (Unix domain socket or TCP)"""
        logger.info("Setting up socket server")
        
        try:
            # Create and start the server thread
            if self.use_tcp:
                logger.info(f"Using TCP socket server on {self.tcp_host}:{self.tcp_port}")
                self.server_thread = threading.Thread(target=self.run_tcp_server)
            else:
                logger.info(f"Using Unix domain socket server at {self.socket_path}")
                self.server_thread = threading.Thread(target=self.run_unix_socket_server)
                
            # Mark as daemon so it terminates when the main thread exits
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logger.info("Socket server thread started")
            return True
        except Exception as e:
            logger.error(f"Error setting up socket server: {e}")
            logger.error(traceback.format_exc())
            return False
            
    def _process_commands(self):
        """Process commands from the socket server"""
        logger.info("Starting command processing loop")
        
        # Check if socket_server is initialized
        if self.socket_server is None:
            logger.error("Socket server is not initialized, command processing loop cannot start")
            return
            
        # Lists for select
        inputs = [self.socket_server]
        outputs = []
        
        # Add a safety timeout to prevent indefinite hanging
        last_activity_time = time.time()
        safety_timeout = int(os.environ.get('EINK_SAFETY_TIMEOUT', str(INACTIVITY_TIMEOUT)))
        
        try:
            while not self.stop_event.is_set():
                # Use select with a timeout to allow checking the stop event
                try:
                    readable, writable, exceptional = select.select(
                        inputs, outputs, inputs, 1.0)
                    
                    # Inactivity check - if no activity for a while, log and maybe exit
                    if not readable and not writable and not exceptional:
                        if time.time() - last_activity_time > safety_timeout:
                            logger.warning(f"No activity for {safety_timeout} seconds, checking system health")
                            # Just log for now, don't exit
                            last_activity_time = time.time()  # Reset timer
                    else:
                        # Activity detected, reset the timer
                        last_activity_time = time.time()
                        
                    for s in readable:
                        if s is self.socket_server:
                            # New connection
                            client_socket, address = self.socket_server.accept()
                            client_socket.setblocking(0)
                            inputs.append(client_socket)
                            logger.info(f"New connection from {address}")
                        else:
                            # Existing client sending data
                            try:
                                data = s.recv(MAX_MSG_SIZE)
                                if data:
                                    # Process the received command
                                    self._handle_command(s, data)
                                else:
                                    # Connection closed by client
                                    logger.info("Client closed connection")
                                    inputs.remove(s)
                                    s.close()
                            except Exception as e:
                                logger.error(f"Error handling client data: {e}")
                                if s in inputs:
                                    inputs.remove(s)
                                s.close()
                    
                    # Check for exceptional conditions
                    for s in exceptional:
                        logger.warning(f"Exceptional condition on socket")
                        inputs.remove(s)
                        s.close()
                
                except select.error as e:
                    # Handle select errors
                    logger.error(f"Select error: {e}")
                    # If the error is related to signal interrupts, just continue
                    if e.args[0] == errno.EINTR:
                        continue
                    else:
                        # For other errors, break the loop
                        logger.error("Exiting command loop due to select error")
                        break
                
                # Process any queued commands
                self._process_queued_commands()
                
                # Give the system a short break to prevent CPU hogging
                time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"Error in command processing loop: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Clean up when the loop exits
            self.cleanup()

    def _handle_command(self, client_socket, data):
        """Handle a command received from a client"""
        try:
            # Decode the data
            message = data.decode('utf-8')
            logger.debug(f"Received command: {message}")
            
            # Parse the JSON message
            try:
                command = json.loads(message)
            except Exception as e:
                logger.error(f"Invalid JSON command: {e}")
                self._send_response(client_socket, {
                    'status': 'error',
                    'message': f'Invalid JSON: {str(e)}'
                })
                return
            
            # Process the command
            action = command.get('action')
            
            # Queue the command for processing
            self.command_queue.append((client_socket, command))
            
            # Acknowledge receipt of the command
            self._send_response(client_socket, {
                'status': 'queued',
                'message': f'Command {action} queued for processing'
            })
            
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            logger.error(traceback.format_exc())
            try:
                self._send_response(client_socket, {
                    'status': 'error',
                    'message': f'Error handling command: {str(e)}'
                })
            except:
                pass

    def _send_response(self, client_socket, response):
        """Send a response back to a client"""
        try:
            message = json.dumps(response).encode('utf-8')
            client_socket.sendall(message)
        except Exception as e:
            logger.error(f"Error sending response: {e}")

    def _process_queued_commands(self):
        """Process commands in the queue"""
        while self.command_queue:
            try:
                with self.lock:
                    client_socket, command = self.command_queue.pop(0)
                
                result = self._execute_command(command)
                
                # Send the result back to the client
                self._send_response(client_socket, result)
                
            except Exception as e:
                logger.error(f"Error processing queued command: {e}")
                logger.error(traceback.format_exc())

    def _execute_command(self, command):
        """Execute a display command"""
        if not self.initialized:
            return {
                'status': 'error',
                'message': 'Display not initialized'
            }
        
        action = command.get('action')
        
        try:
            if action == 'clear':
                self.display.Clear()
                return {
                    'status': 'success',
                    'message': 'Display cleared'
                }
                
            elif action == 'display_text':
                text = command.get('text', '')
                x = command.get('x', 10)
                y = command.get('y', 10)
                font_size = command.get('font_size', 24)
                
                if hasattr(self.display, 'display_text'):
                    self.display.display_text(text, x, y, font_size)
                else:
                    # Fallback for displays without display_text method
                    logger.warning("Display lacks display_text method, using mock implementation")
                    # Mock implementation or return an error
                    return {
                        'status': 'error',
                        'message': 'Display does not support text display'
                    }
                
                return {
                    'status': 'success',
                    'message': f'Displayed text: {text}'
                }
                
            elif action == 'sleep':
                self.display.sleep()
                return {
                    'status': 'success',
                    'message': 'Display put to sleep'
                }
                
            elif action == 'wake':
                self.display.init()
                return {
                    'status': 'success',
                    'message': 'Display woken up'
                }
                
            elif action == 'status':
                return {
                    'status': 'success',
                    'initialized': self.initialized,
                    'mock_mode': self.mock_mode,
                    'display_type': type(self.display).__name__ if self.display else None
                }
                
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown action: {action}'
                }
                
        except Exception as e:
            logger.error(f"Error executing command {action}: {e}")
            logger.error(traceback.format_exc())
            return {
                'status': 'error',
                'message': f'Error executing {action}: {str(e)}'
            }

    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources")
        
        # Clean up display - try both self.display and self.eink for compatibility
        try:
            # First try using display directly
            if hasattr(self, 'display') and self.display is not None:
                try:
                    logger.info("Closing display")
                    if hasattr(self.display, 'close'):
                        self.display.close()
                    elif hasattr(self.display, 'cleanup'):
                        self.display.cleanup()
                except Exception as e:
                    logger.error(f"Error closing display: {e}")
                self.display = None
            
            # Also try eink for backward compatibility
            if hasattr(self, 'eink') and self.eink is not None:
                try:
                    logger.info("Cleaning up eink driver")
                    if hasattr(self.eink, 'driver') and self.eink.driver is not None:
                        if hasattr(self.eink.driver, 'close'):
                            self.eink.driver.close()
                        elif hasattr(self.eink.driver, 'cleanup'):
                            self.eink.driver.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up eink driver: {e}")
                self.eink = None
                
        except Exception as e:
            logger.error(f"Error during display cleanup: {e}")
        
        # Close the socket server
        if hasattr(self, 'socket_server') and self.socket_server is not None:
            try:
                logger.info("Closing socket server")
                self.socket_server.close()
            except Exception as e:
                logger.error(f"Error closing socket server: {e}")
        
        # Remove the socket file
        if not self.use_tcp and hasattr(self, 'socket_path'):
            try:
                if os.path.exists(self.socket_path):
                    logger.info(f"Removing socket file: {self.socket_path}")
                    os.unlink(self.socket_path)
            except Exception as e:
                logger.error(f"Error removing socket file: {e}")

    def _initialize_display(self) -> bool:
        """
        Initialize the e-ink display with retry logic
        
        Returns:
            bool: Success or failure
        """
        # Determine which display driver to use
        display_type = os.environ.get('EINK_DISPLAY_TYPE', 'waveshare_3in7').lower()
        
        # Use mock mode if specified
        if self.mock_mode:
            logger.info("Using mock e-ink display driver")
            try:
                self.display = MockEPD()
                self.display.init()
                
                # Set up backward compatibility wrapper
                class EinkWrapper:
                    def __init__(self, display):
                        self.driver = display
                    
                    def initialize(self):
                        if hasattr(self.driver, 'init'):
                            return self.driver.init()
                        return None
                
                self.eink = EinkWrapper(self.display)
                
                self.initialized = True
                logger.info("Mock display initialized successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize mock display: {e}")
                return False
        
        # Check GPIO permissions before attempting to initialize
        gpio_available, message = self._check_gpio_availability()
        logger.info(f"GPIO availability check: {message}")
        
        if not gpio_available:
            # Try to free GPIO resources if needed
            if self.force_kill_gpio:
                kill_success, kill_message = self._kill_gpio_processes()
                logger.info(f"Attempted to free GPIO resources: {kill_message}")
                
                # Check again after cleanup
                gpio_available, message = self._check_gpio_availability()
                logger.info(f"GPIO availability after cleanup: {message}")
                
                if not gpio_available and not self.mock_mode:
                    logger.warning("GPIO resources still unavailable, switching to mock mode")
                    self.mock_mode = True
                    return self._initialize_display()  # Retry with mock mode
        
        # Try to set GPIO permissions if running as root
        try:
            if os.geteuid() == 0:  # Running as root
                logger.info("Running as root, ensuring GPIO permissions are set")
                subprocess.run(['chmod', 'a+rw', '/dev/gpiomem'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
                subprocess.run(['chmod', 'a+rw', '/dev/gpiochip0'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
        except Exception as e:
            logger.warning(f"Failed to set GPIO permissions: {e}")
        
        # Retry logic for hardware display
        for attempt in range(self.max_init_retries):
            try:
                logger.info(f"Initializing display (attempt {attempt+1}/{self.max_init_retries})...")
                
                if display_type in ['waveshare_3in7', 'waveshare', '3in7']:
                    # Attempt to use legacy GPIO access by importing RPi.GPIO first
                    try:
                        import RPi.GPIO as GPIO
                        GPIO.setmode(GPIO.BCM)
                        GPIO.setwarnings(False)
                        logger.info("Successfully imported and configured RPi.GPIO")
                    except ImportError:
                        logger.warning("Could not import RPi.GPIO, will rely on driver's GPIO handling")
                    except Exception as e:
                        logger.warning(f"Error configuring GPIO: {e}")
                    
                    # Directly use the WaveshareEPD3in7 class
                    self.display = WaveshareEPD3in7()
                else:
                    logger.error(f"Unknown display type: {display_type}, falling back to waveshare_3in7")
                    self.display = WaveshareEPD3in7()
                
                # Test display to confirm it works
                self.display.init()
                self.display.Clear()
                
                # Set up backward compatibility wrapper
                class EinkWrapper:
                    def __init__(self, display):
                        self.driver = display
                    
                    def initialize(self):
                        if hasattr(self.driver, 'init'):
                            return self.driver.init()
                        return None
                
                self.eink = EinkWrapper(self.display)
                
                logger.info("Display initialized successfully")
                self.initialized = True
                return True
                
            except Exception as e:
                logger.error(f"Failed to initialize display (attempt {attempt+1}): {e}")
                logger.error(traceback.format_exc())
                
                # Try to free GPIO resources if force_kill_gpio is enabled
                if self.force_kill_gpio:
                    kill_success, kill_message = self._kill_gpio_processes()
                    logger.info(f"Attempted to free GPIO resources: {kill_message}")
                    
                # Clean up any partial initialization
                try:
                    if hasattr(self, 'display') and self.display is not None:
                        self.display.close()
                except:
                    pass
                
                self.display = None
                
                # Wait before retry (skip delay on last attempt)
                if attempt < self.max_init_retries - 1:
                    logger.info(f"Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)

        logger.error(f"Failed to initialize display after {self.max_init_retries} attempts")
        
        # Fall back to mock mode if hardware initialization failed
        if not self.mock_mode:
            logger.info("Falling back to mock display mode after hardware initialization failure")
            self.mock_mode = True
            return self._initialize_display()
            
        return False


def run_service(debug_timeout=None):
    """
    Run the EInk service as a standalone process
    
    Args:
        debug_timeout (int, optional): If provided, will exit the service after this many seconds.
                                      Useful for testing and debugging.
    """
    start_time = time.time()
    
    # Create and start service
    try:
        # Set up signal handlers to capture termination signals
        def handle_termination(signum, frame):
            logger.info(f"Received signal {signum}, shutting down EInk service")
            # If service exists, stop it gracefully
            if 'service' in locals() and hasattr(service, 'stop'):
                service.stop()
            # Exit the process
            sys.exit(0)
            
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_termination)
        signal.signal(signal.SIGTERM, handle_termination)
        
        # Create and start the service
        service = EInkService()
        logger.info("Starting EInk service...")
        if not service.start():
            logger.error("Failed to start EInk service properly")
            sys.exit(1)
        
        # If debug_timeout is set, print a message about it
        if debug_timeout:
            logger.info(f"Debug mode: Service will automatically exit after {debug_timeout} seconds")
        
        # Keep the main thread running with a timeout
        max_runtime = int(os.environ.get('EINK_MAX_RUNTIME', 24 * 60 * 60))  # Default 24 hours
        
        # Use the shorter of debug_timeout or max_runtime if debug_timeout is set
        if debug_timeout:
            max_runtime = min(debug_timeout, max_runtime)
        
        while service.initialized:
            # Check if we've been running too long
            elapsed = time.time() - start_time
            if elapsed > max_runtime:
                if debug_timeout:
                    logger.info(f"Debug timeout of {debug_timeout}s reached, shutting down service")
                else:
                    logger.warning(f"Service has been running for over {max_runtime} seconds, shutting down")
                break
                
            # Print periodic status updates in debug timeout mode
            if debug_timeout and int(elapsed) % 5 == 0 and int(elapsed) > 0:
                remaining = max_runtime - elapsed
                logger.info(f"Service running for {int(elapsed)}s, {int(remaining)}s until auto-shutdown")
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Error running EInk service: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Always clean up hardware resources on exit
        if 'service' in locals() and service.initialized:
            logger.info("Shutting down EInk service")
            service.stop()
        
        # Log the total runtime
        runtime = time.time() - start_time
        logger.info(f"EInk service has been terminated after running for {int(runtime)}s")
        
        # Make sure we exit the process
        sys.exit(0)


if __name__ == "__main__":
    # Check for command line arguments for debug mode
    debug_timeout = None
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.startswith('--timeout='):
                try:
                    debug_timeout = int(arg.split('=')[1])
                    print(f"Debug mode: Service will exit after {debug_timeout} seconds")
                except (IndexError, ValueError):
                    pass
            elif arg == '--debug':
                # Default debug timeout of 30 seconds
                debug_timeout = 30
                print(f"Debug mode: Service will exit after {debug_timeout} seconds")
    
    # Run with the timeout if specified
    run_service(debug_timeout) 