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
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

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
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    logger = logging.getLogger("eink_service")

from devices.eink.eink import EInk

# Constants
DEFAULT_SOCKET_PATH = "/tmp/eink_service.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 9500
INACTIVITY_TIMEOUT = 300  # 5 minutes


class EInkService:
    """
    Service that maintains exclusive access to the e-ink display and
    provides a socket-based interface for display operations.
    """
    
    def __init__(self, driver_name=None, use_unix_socket=True):
        """
        Initialize the EInk service
        
        Args:
            driver_name: Specific driver to use (e.g., 'waveshare_3in7')
            use_unix_socket: Whether to use Unix sockets (True) or TCP (False)
        """
        logger.info("Initializing EInk Service")
        self.driver_name = driver_name
        self.use_unix_socket = use_unix_socket
        self.socket_path = DEFAULT_SOCKET_PATH
        self.tcp_host = DEFAULT_TCP_HOST
        self.tcp_port = DEFAULT_TCP_PORT
        
        # Initialize e-ink display with appropriate driver
        try:
            self.eink = None  # Will be initialized in start()
            
            # Command queue for processing display operations
            self.command_queue = queue.Queue()
            
            # Control flags
            self.running = False
            self.last_operation_time = time.time()
            
            # Setup signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            logger.info("EInk Service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing EInk Service: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def start(self):
        """Start the EInk service, including display initialization and server threads"""
        if self.running:
            logger.warning("EInk Service is already running")
            return
            
        logger.info("Starting EInk Service")
        self.running = True
        
        try:
            # Initialize the e-ink device first
            logger.info(f"Initializing EInk device with driver: {self.driver_name}")
            self.eink = EInk(self.driver_name)
            self.eink.initialize()
            
            # Get display dimensions for reference
            width = self.eink.driver.width
            height = self.eink.driver.height
            logger.info(f"Display dimensions: {width}x{height}")
            
            # Start command processing thread
            self.command_thread = threading.Thread(target=self.process_commands)
            self.command_thread.daemon = True
            self.command_thread.start()
            
            # Start the appropriate server
            if self.use_unix_socket:
                self.server_thread = threading.Thread(target=self.run_unix_socket_server)
            else:
                self.server_thread = threading.Thread(target=self.run_tcp_server)
            
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logger.info("EInk Service started successfully")
        except Exception as e:
            logger.error(f"Error starting EInk Service: {e}")
            logger.error(traceback.format_exc())
            self.running = False
            raise
    
    def stop(self):
        """Stop the EInk service and clean up resources"""
        if not self.running:
            logger.warning("EInk Service is not running")
            return
            
        logger.info("Stopping EInk Service")
        self.running = False
        
        # Wait for threads to finish
        if hasattr(self, 'command_thread') and self.command_thread.is_alive():
            self.command_thread.join(timeout=5.0)
            
        if hasattr(self, 'server_thread') and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
            
        # Clean up resources
        if self.eink:
            try:
                # Put display to sleep
                self.eink.driver.sleep()
            except:
                pass
            self.eink = None
            
        # Remove socket file if using Unix sockets
        if self.use_unix_socket and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
            
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
            os.unlink(self.socket_path)
        
        # Create socket server
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(5)
        server.settimeout(1.0)  # Allow checking running flag
        
        logger.info("Unix socket server ready")
        
        while self.running:
            try:
                client, _ = server.accept()
                self._handle_client(client)
            except socket.timeout:
                # This just allows us to check the running flag
                continue
            except Exception as e:
                if self.running:  # Only log if we're not in shutdown
                    logger.error(f"Socket server error: {e}")
                    logger.error(traceback.format_exc())
        
        # Clean up
        server.close()
        logger.info("Unix socket server stopped")
    
    def run_tcp_server(self):
        """Run a TCP server for network communication"""
        logger.info(f"Starting TCP server at {self.tcp_host}:{self.tcp_port}")
        
        # Create socket server
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.tcp_host, self.tcp_port))
        server.listen(5)
        server.settimeout(1.0)  # Allow checking running flag
        
        logger.info("TCP server ready")
        
        while self.running:
            try:
                client, addr = server.accept()
                logger.debug(f"Connection from {addr}")
                self._handle_client(client)
            except socket.timeout:
                # This just allows us to check the running flag
                continue
            except Exception as e:
                if self.running:  # Only log if we're not in shutdown
                    logger.error(f"Socket server error: {e}")
                    logger.error(traceback.format_exc())
        
        # Clean up
        server.close()
        logger.info("TCP server stopped")
    
    def _handle_client(self, client):
        """Handle a client connection and process their command"""
        try:
            # Set a timeout for receiving data
            client.settimeout(5.0)
            
            # Read data from client
            data = b""
            while True:
                chunk = client.recv(4096)
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
                self.command_queue.put(command)
                
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
    
    def process_commands(self):
        """Process commands from the queue"""
        logger.info("Command processor started")
        
        while self.running:
            try:
                # Get command with timeout to allow checking running flag
                try:
                    command = self.command_queue.get(timeout=1.0)
                except queue.Empty:
                    # Check if we should sleep the display after inactivity
                    if time.time() - self.last_operation_time > INACTIVITY_TIMEOUT:
                        try:
                            logger.info("Display inactive, putting to sleep")
                            self.eink.driver.sleep()
                        except Exception as e:
                            logger.error(f"Error putting display to sleep: {e}")
                    continue
                
                # Process the command
                logger.info(f"Processing command: {command.get('action', 'unknown')}")
                self.handle_command(command)
                self.command_queue.task_done()
                
                # Update last operation time
                self.last_operation_time = time.time()
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                logger.error(traceback.format_exc())
        
        logger.info("Command processor stopped")
    
    def handle_command(self, command):
        """Handle a display command"""
        action = command.get('action')
        
        if not action:
            logger.warning("Command missing 'action' field")
            return
        
        if action == 'clear':
            logger.info("Clearing display")
            self.eink.clear_display()
            
        elif action == 'display_text':
            text = command.get('text', '')
            font_size = command.get('font_size', 24)
            x = command.get('x', 10)
            y = command.get('y', 10)
            font_name = command.get('font', None)
            
            logger.info(f"Displaying text: '{text}' at ({x}, {y}) with size {font_size}")
            
            # Create image
            image = Image.new('1', (self.eink.driver.width, self.eink.driver.height), 255)
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
            self.eink.display_image(image)
            
        elif action == 'display_image':
            # Check for image data (base64 encoded)
            image_data = command.get('image_data')
            image_path = command.get('image_path')
            
            if image_data:
                logger.info("Displaying image from base64 data")
                try:
                    # Decode base64 image data
                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(BytesIO(image_bytes))
                    self.eink.display_image(image)
                except Exception as e:
                    logger.error(f"Error displaying image from data: {e}")
            elif image_path:
                logger.info(f"Displaying image from path: {image_path}")
                try:
                    # Load image from file
                    image = Image.open(image_path)
                    self.eink.display_image(image)
                except Exception as e:
                    logger.error(f"Error displaying image from path: {e}")
            else:
                logger.warning("No image data or path provided")
                
        elif action == 'sleep':
            logger.info("Putting display to sleep")
            self.eink.driver.sleep()
            
        elif action == 'wake':
            logger.info("Waking up display")
            self.eink.initialize()
            
        elif action == 'status':
            # This doesn't do anything to the display, just for diagnostics
            logger.info("Status request received")
            # Could implement returning status data in the future
            
        else:
            logger.warning(f"Unknown action: {action}")


def run_service():
    """Run the EInk service as a standalone process"""
    # Get driver type from environment variable if set
    driver_name = os.environ.get('EINK_DISPLAY_TYPE')
    
    # Determine socket type from environment
    use_unix_socket = os.environ.get('EINK_USE_TCP', '0') != '1'
    
    # Create and start service
    try:
        service = EInkService(driver_name=driver_name, use_unix_socket=use_unix_socket)
        service.start()
        
        # Keep the main thread running
        while service.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error running EInk service: {e}")
        logger.error(traceback.format_exc())
    finally:
        if 'service' in locals() and service.running:
            service.stop()


if __name__ == "__main__":
    run_service() 