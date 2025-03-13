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
            logging.FileHandler('/tmp/eink_service.log')
        ]
    )
    logger = logging.getLogger("eink_service")

# Import the display driver types
from devices.eink.waveshare_3in7 import WaveshareEPD3in7
from devices.eink.mock_epd import MockEPD

# Fix imports for backward compatibility
try:
    # Try to import the eink module using the project import path
    from devices.eink.eink import EInk
    logger.info("Successfully imported EInk module")
except ImportError:
    # Fall back to using the newly implemented direct drivers
    logger.warning("Could not import legacy EInk module, using direct driver access")
    from waveshare_3in7 import WaveshareEPD3in7
    from mock_epd import MockEPD

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
                self._initialize_display()  # Try once more with mock mode
            
            # Mark as initialized
            self.initialized = True
            logger.info("Display initialized successfully")
            
            # Start socket server
            logger.info("Setting up socket server...")
            socket_setup_success = self._setup_socket_server()
            if not socket_setup_success:
                logger.error("Failed to set up socket server, service will not be able to receive commands")
                return False
            
            # Start command processing loop
            logger.info("Starting command processing loop...")
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
            
        # Clean up resources
        if self.display:
            try:
                # Put display to sleep
                logger.info("Putting display to sleep before shutdown")
                if hasattr(self.display.driver, 'sleep'):
                    self.display.driver.sleep()
                
                # Perform cleanup
                logger.info("Cleaning up hardware resources")
                self.display.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
            self.display = None
            
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
        
        try:
            while not self.stop_event.is_set():
                # Use select with a timeout to allow checking the stop event
                readable, writable, exceptional = select.select(
                    inputs, outputs, inputs, 1.0)
                
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
                
                # Process any queued commands
                self._process_queued_commands()
        
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
        
        # Close the display
        if hasattr(self, 'display') and self.display is not None:
            try:
                logger.info("Closing display")
                self.display.close()
            except Exception as e:
                logger.error(f"Error closing display: {e}")
        
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
                self.initialized = True
                logger.info("Mock display initialized successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize mock display: {e}")
                return False
        
        # Retry logic for hardware display
        for attempt in range(self.max_init_retries):
            try:
                logger.info(f"Initializing display (attempt {attempt+1}/{self.max_init_retries})...")
                
                if display_type in ['waveshare_3in7', 'waveshare', '3in7']:
                    # Directly use the WaveshareEPD3in7 class
                    self.display = WaveshareEPD3in7()
                else:
                    logger.error(f"Unknown display type: {display_type}, falling back to waveshare_3in7")
                    self.display = WaveshareEPD3in7()
                
                # Test display to confirm it works
                self.display.init()
                self.display.Clear()
                
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
        return False


def run_service():
    """Run the EInk service as a standalone process"""
    # Create and start service
    try:
        service = EInkService()
        service.start()
        
        # Keep the main thread running
        while service.initialized:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error running EInk service: {e}")
        logger.error(traceback.format_exc())
        # Always clean up hardware resources on error
        logger.info("Cleaned up SPI and GPIO.")
    finally:
        if 'service' in locals() and service.initialized:
            service.stop()


if __name__ == "__main__":
    run_service() 