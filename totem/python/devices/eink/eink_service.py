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

# Only import EInk class after setting up paths
try:
    from devices.eink.eink import EInk
except ImportError as e:
    logger.error(f"Error importing EInk: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(traceback.format_exc())
    sys.exit(1)

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
        """Start the EInk service, including display initialization and server threads"""
        if self.initialized:
            logger.warning("EInk Service is already running")
            return
            
        logger.info("Starting EInk Service")
        self.initialized = True
        
        try:
            # Check GPIO availability before initializing
            gpio_available, message = self._check_gpio_availability()
            logger.info(f"GPIO check: {message}")
            
            # If GPIO is not available and force killing is enabled
            if not gpio_available and self.force_kill_gpio:
                logger.warning("Attempting to kill processes using GPIO...")
                kill_success, kill_message = self._kill_gpio_processes()
                logger.info(f"GPIO process cleanup: {kill_message}")
                
                # Check again after killing
                gpio_available, message = self._check_gpio_availability()
                logger.info(f"GPIO availability after cleanup: {message}")
            
            # Initialize the e-ink device with retries
            retry_count = 0
            initialized = False
            last_error = None
            
            while retry_count < self.max_init_retries and not initialized:
                try:
                    # Initialize the e-ink device
                    logger.info(f"Initializing EInk device (Attempt {retry_count + 1}/{self.max_init_retries})")
                    self.display = EInk(os.environ.get('EINK_DISPLAY_TYPE', 'waveshare_3in7'), mock_mode=self.mock_mode)
                    self.display.initialize()
                    
                    # Get display dimensions for reference
                    width = self.display.driver.width
                    height = self.display.driver.height
                    logger.info(f"Display dimensions: {width}x{height}")
                    
                    initialized = True
                except Exception as e:
                    last_error = e
                    logger.error(f"Initialization attempt {retry_count + 1} failed: {e}")
                    
                    # Clean up before retry
                    if self.display:
                        try:
                            self.display.cleanup()
                        except:
                            pass
                    
                    # If we're in mock mode, consider it initialized
                    if self.mock_mode:
                        logger.info("Mock mode enabled, continuing despite initialization failure")
                        initialized = True
                        break
                    
                    # Wait before retrying
                    retry_count += 1
                    if retry_count < self.max_init_retries:
                        logger.info(f"Waiting {RETRY_DELAY}s before retry #{retry_count + 1}...")
                        time.sleep(RETRY_DELAY)
            
            # If we couldn't initialize and we're not in mock mode, fail
            if not initialized and not self.mock_mode:
                if os.environ.get('EINK_ALLOW_MOCK_FALLBACK', '1') == '1':
                    logger.warning("Hardware initialization failed, falling back to mock mode")
                    self.mock_mode = True
                    self.display = EInk(os.environ.get('EINK_DISPLAY_TYPE', 'waveshare_3in7'), mock_mode=True)
                    # No need to call initialize() for mock mode
                else:
                    raise Exception(f"Failed to initialize EInk device after {self.max_init_retries} attempts: {last_error}")
            
            # Start command processing loop
            self._process_commands()
            
            # Start the appropriate server
            if self.use_tcp:
                self.server_thread = threading.Thread(target=self.run_tcp_server)
            else:
                self.server_thread = threading.Thread(target=self.run_unix_socket_server)
            
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logger.info("EInk Service started successfully")
        except Exception as e:
            logger.error(f"Error starting EInk Service: {e}")
            logger.error(traceback.format_exc())
            self.initialized = False
            raise
    
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
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(self.socket_path)
            server.listen(5)
            server.settimeout(1.0)  # Allow checking running flag
            
            # Ensure socket file has the right permissions
            try:
                os.chmod(self.socket_path, 0o666)  # Allow anyone to read/write
                logger.info(f"Set socket file permissions to 0o666")
            except Exception as e:
                logger.warning(f"Could not set socket file permissions: {e}")
            
            logger.info("Unix socket server ready")
            
            while self.initialized:
                try:
                    client, _ = server.accept()
                    self._handle_client(client)
                except socket.timeout:
                    # This just allows us to check the running flag
                    continue
                except Exception as e:
                    if self.initialized:  # Only log if we're not in shutdown
                        logger.error(f"Socket server error: {e}")
                        logger.error(traceback.format_exc())
            
            # Clean up
            server.close()
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
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.tcp_host, self.tcp_port))
            server.listen(5)
            server.settimeout(1.0)  # Allow checking running flag
            
            logger.info("TCP server ready")
            
            while self.initialized:
                try:
                    client, addr = server.accept()
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
            server.close()
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
    
    def _process_commands(self):
        """Process commands from the socket server"""
        logger.info("Starting command processing loop")
        
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
                logger.info("Clearing display")
                if self.mock_mode:
                    logger.info("Mock clear display")
                else:
                    self.display.clear_display()
                return {
                    'status': 'success',
                    'message': 'Display cleared'
                }
                
            elif action == 'display_text':
                text = command.get('text', '')
                font_size = command.get('font_size', 24)
                x = command.get('x', 10)
                y = command.get('y', 10)
                font_name = command.get('font', None)
                
                logger.info(f"Displaying text: '{text}' at ({x}, {y}) with size {font_size}")
                
                try:
                    # Create image
                    image = Image.new('1', (self.display.driver.width, self.display.driver.height), 255)
                    draw = ImageDraw.Draw(image)
                    
                    # Load font
                    try:
                        if font_name:
                            font = ImageFont.truetype(font_name, font_size)
                        else:
                            font = ImageFont.load_default()
                    except Exception as e:
                        logger.warning(f"Could not load font, using default: {e}")
                        font = ImageFont.load_default()
                    
                    # Draw text
                    draw.text((x, y), text, font=font, fill=0)
                    
                    # Display image
                    if self.mock_mode:
                        logger.info(f"Mock display text '{text}'")
                    else:
                        self.display.display_image(image)
                    return {
                        'status': 'success',
                        'message': f'Displayed text: {text}'
                    }
                except Exception as e:
                    logger.error(f"Error displaying text: {e}")
                    return {
                        'status': 'error',
                        'message': f'Error displaying text: {str(e)}'
                    }
            
            elif action == 'display_image':
                # Check for image data (base64 encoded)
                image_data = command.get('image_data')
                image_path = command.get('image_path')
                
                try:
                    if image_data:
                        logger.info("Displaying image from base64 data")
                        try:
                            # Decode base64 image data
                            image_bytes = base64.b64decode(image_data)
                            image = Image.open(BytesIO(image_bytes))
                            if self.mock_mode:
                                logger.info(f"Mock display image from data")
                            else:
                                self.display.display_image(image)
                            return {
                                'status': 'success',
                                'message': 'Displayed image from base64 data'
                            }
                        except Exception as e:
                            logger.error(f"Error displaying image from data: {e}")
                            return {
                                'status': 'error',
                                'message': f'Error displaying image from data: {str(e)}'
                            }
                    elif image_path:
                        logger.info(f"Displaying image from path: {image_path}")
                        try:
                            # Load image from file
                            image = Image.open(image_path)
                            if self.mock_mode:
                                logger.info(f"Mock display image from path {image_path}")
                            else:
                                self.display.display_image(image)
                            return {
                                'status': 'success',
                                'message': f'Displayed image from path: {image_path}'
                            }
                        except Exception as e:
                            logger.error(f"Error displaying image from path: {e}")
                            return {
                                'status': 'error',
                                'message': f'Error displaying image from path: {str(e)}'
                            }
                    else:
                        logger.warning("No image data or path provided")
                        return {
                            'status': 'error',
                            'message': 'No image data or path provided'
                        }
                except Exception as e:
                    logger.error(f"Error in display_image: {e}")
                    return {
                        'status': 'error',
                        'message': f'Error in display_image: {str(e)}'
                    }
            
            elif action == 'sleep':
                logger.info("Putting display to sleep")
                if self.mock_mode:
                    logger.info("Mock sleep")
                elif hasattr(self.display.driver, 'sleep'):
                    self.display.driver.sleep()
                else:
                    logger.warning("Sleep not supported by this driver")
                return {
                    'status': 'success',
                    'message': 'Display put to sleep'
                }
            
            elif action == 'wake':
                logger.info("Waking up display")
                if self.mock_mode:
                    logger.info("Mock wake")
                else:
                    self.display.initialize()
                return {
                    'status': 'success',
                    'message': 'Display woken up'
                }
            
            elif action == 'status':
                # This doesn't do anything to the display, just for diagnostics
                logger.info("Status request received")
                # Could implement returning status data in the future
                return {
                    'status': 'success',
                    'initialized': self.initialized,
                    'mock_mode': self.mock_mode,
                    'display_type': type(self.display).__name__ if self.display else None
                }
            
            else:
                logger.warning(f"Unknown action: {action}")
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