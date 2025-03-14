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
from PIL import Image, ImageDraw, ImageFont, ImageOps
from typing import Dict, Any, Optional, List, Tuple, Union
import errno
import stat

# Add the parent directory to path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
devices_dir = os.path.dirname(os.path.dirname(script_dir))
python_dir = os.path.dirname(devices_dir)
sys.path.insert(0, python_dir)

# Define log file path
LOG_FILE_PATH = '/tmp/totem-eink-service.log'

# E-Ink refresh settings
# How often to do a full refresh (every N partial refreshes)
FULL_REFRESH_INTERVAL = 20  # Increasing from 5 to 20
# Whether to clear the screen before doing a full refresh
CLEAR_ON_FULL_REFRESH = True

try:
    from utils.logger import logger
except ImportError:
    # Create a logger if the main logger is not available
    try:
        # Ensure the log file is writable
        with open(LOG_FILE_PATH, 'a') as f:
            f.write("Log file initialized\n")
        
        logging.basicConfig(
            level=logging.INFO if os.environ.get('LOGLEVEL', 'INFO') != 'DEBUG' else logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(LOG_FILE_PATH)
            ]
        )
        logger = logging.getLogger("eink_service")
        logger.info(f"Logger initialized with log file at {LOG_FILE_PATH}")
    except Exception as e:
        # If we can't write to the log file, fall back to console only
        print(f"Error setting up log file at {LOG_FILE_PATH}: {e}")
        logging.basicConfig(
            level=logging.INFO if os.environ.get('LOGLEVEL', 'INFO') != 'DEBUG' else logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("eink_service")
        logger.error(f"Failed to set up log file at {LOG_FILE_PATH}: {e}")
        logger.info("Falling back to console logging only")

# Try to import the proper EInk driver classes
try:
    # Import directly from drivers subdirectory
    from devices.eink.drivers.waveshare_3in7 import WaveshareEPD3in7
    from devices.eink.mock_epd import MockEPD
    logger.info("Successfully imported device drivers")
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
        self.pid_path = os.environ.get('EINK_PID_PATH', "/tmp/eink_service.pid")
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
        
        # Refresh counter for tracking when to do a full refresh
        self.update_counter = 0
        self.full_refresh_interval = FULL_REFRESH_INTERVAL
        self.clear_on_full_refresh = CLEAR_ON_FULL_REFRESH
        logger.info(f"Full refresh will occur every {self.full_refresh_interval} updates")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Write PID file for external process management
        try:
            with open(self.pid_path, 'w') as pid_file:
                pid_file.write(str(os.getpid()))
            logger.debug(f"Wrote PID {os.getpid()} to {self.pid_path}")
        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")
        
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
        
        # Set initialized flag to false initially
        self.initialized = False
        
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
            
            # Mark as initialized - this is what the main loop checks for termination
            self.initialized = True
            logger.info("Display initialized successfully")
            
            # Start socket server
            logger.info("Setting up socket server...")
            socket_setup_success = self._setup_socket_server()
            if not socket_setup_success:
                logger.error("Failed to set up socket server, service will not be able to receive commands")
                self.initialized = False  # Important: Mark as not initialized if we fail
                return False
            
            # Wait for socket server to be ready (with timeout)
            logger.info("Waiting for socket server to be ready...")
            if not self.socket_server_ready.wait(timeout=5.0):
                logger.error("Timed out waiting for socket server to be ready")
                self.initialized = False  # Important: Mark as not initialized if we fail
                return False
                
            logger.info("Socket server is ready, starting command processing loop...")
            
            # Start command processing loop
            self._process_commands()
            
        except Exception as e:
            logger.error(f"Error starting EInk service: {e}")
            logger.error(traceback.format_exc())
            
            # Clean up resources as best we can
            self.cleanup()
            self.initialized = False  # Important: Mark as not initialized if we fail
            return False
            
        return True
    
    def stop(self):
        """Stop the service and clean up resources."""
        if not hasattr(self, 'initialized') or not self.initialized:
            logger.warning("EInk service not initialized, nothing to stop")
            return

        logger.info("Stopping EInk service")
        stop_start_time = time.time()
        
        # Set the stop event to signal threads to exit
        if hasattr(self, 'stop_event'):
            logger.info("Setting stop event")
            self.stop_event.set()
        
        # Forcefully close the socket server first to unblock any accept() calls
        if hasattr(self, 'socket_server') and self.socket_server:
            logger.info("Closing socket server")
            try:
                # Try to shutdown the socket first to unblock any blocking calls
                if hasattr(self.socket_server, 'shutdown'):
                    try:
                        self.socket_server.shutdown(socket.SHUT_RDWR)
                        logger.info("Socket server shutdown called")
                    except Exception as e:
                        logger.warning(f"Socket server shutdown failed: {e}")
                
                # Close the socket
                self.socket_server.close()
                logger.info("Socket server closed")
            except Exception as e:
                logger.error(f"Error closing socket server: {e}")
        
        # Wait for the server thread to finish if it's running
        if hasattr(self, 'server_thread') and self.server_thread and self.server_thread.is_alive():
            logger.info("Waiting for server thread to finish")
            try:
                self.server_thread.join(timeout=3)  # Wait up to 3 seconds
                if self.server_thread.is_alive():
                    logger.warning("Server thread did not finish in time, proceeding with cleanup")
            except Exception as e:
                logger.error(f"Error joining server thread: {e}")
        
        # Force close file descriptors if thread didn't exit
        if hasattr(self, 'server_thread') and self.server_thread and self.server_thread.is_alive():
            logger.warning("Server thread still alive after join timeout, forcing file descriptor closure")
            
            # Try to find and close any open file descriptors
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                for fd in range(3, soft):  # Start at 3 to skip stdin/stdout/stderr
                    try:
                        os.close(fd)
                    except OSError:
                        pass  # File descriptor wasn't open
            except Exception as e:
                logger.error(f"Error while force-closing file descriptors: {e}")
        
        # Perform resource cleanup
        self.cleanup()
        
        # Final check to ensure we're marked as not initialized
        self.initialized = False
        
        # Log total stop time
        stop_duration = time.time() - stop_start_time
        logger.info(f"EInk service stopped (took {stop_duration:.2f}s)")
    
    def signal_handler(self, sig, frame):
        """Handle termination signals for graceful shutdown"""
        logger.info(f"Received signal {sig}, shutting down")
        self.stop()
    
    def run_unix_socket_server(self):
        """Run the Unix domain socket server"""
        logger.info("Starting Unix socket server at {}".format(self.socket_path))
        
        # Check if socket file already exists
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
                logger.info(f"Removed existing socket file: {self.socket_path}")
            except OSError as e:
                logger.error(f"Error removing existing socket file: {e}")
                self.socket_server_ready.set()  # Set event to unblock main thread
                return
        
        # Create socket directory if it doesn't exist
        socket_dir = os.path.dirname(self.socket_path)
        if not os.path.exists(socket_dir):
            try:
                os.makedirs(socket_dir, exist_ok=True)
                logger.info(f"Created socket directory: {socket_dir}")
            except OSError as e:
                logger.error(f"Error creating socket directory: {e}")
                self.socket_server_ready.set()  # Set event to unblock main thread
                return
        
        try:
            # Create the socket
            self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            logger.debug(f"Created Unix socket with file descriptor: {self.socket_server.fileno()}")
            
            # Set socket options
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            logger.debug("Set SO_REUSEADDR option on socket")
            
            # Bind to the socket path
            try:
                self.socket_server.bind(self.socket_path)
                logger.info(f"Bound socket to path: {self.socket_path}")
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    logger.error(f"Socket address already in use: {self.socket_path}")
                    # Try to forcibly remove the socket file and rebind
                    try:
                        os.unlink(self.socket_path)
                        logger.info(f"Forcibly removed existing socket file: {self.socket_path}")
                        self.socket_server.bind(self.socket_path)
                        logger.info(f"Successfully rebound socket to path: {self.socket_path}")
                    except Exception as rebind_error:
                        logger.error(f"Error rebinding socket: {rebind_error}")
                        self.socket_server_ready.set()  # Set the event to unblock the main thread
                        return
                else:
                    logger.error(f"Error binding socket: {e}")
                    self.socket_server_ready.set()  # Set the event to unblock the main thread
                    return
            
            # Set permissions on the socket file
            try:
                os.chmod(self.socket_path, 0o666)
                logger.info(f"Set socket file permissions to 0o666")
                # Log the actual permissions to verify
                st = os.stat(self.socket_path)
                logger.info(f"Socket file stats: mode={oct(st.st_mode)}, uid={st.st_uid}, gid={st.st_gid}")
            except Exception as e:
                logger.error(f"Error setting socket permissions: {e}")
            
            # Start listening
            self.socket_server.listen(5)
            logger.info(f"Socket server listening with backlog of 5")
            
            # Signal that the server is ready
            self.socket_server_ready.set()
            logger.info("Unix socket server ready")
            
            # Set a short timeout to allow checking the stop event
            check_interval = 0.5  # seconds
            self.socket_server.settimeout(check_interval)  # Very short timeout to allow frequent checks
            
            # Main server loop
            while not self.stop_event.is_set():
                
                try:
                    # Check if the socket is still valid
                    if self.socket_server.fileno() == -1:
                        logger.error("Socket descriptor is invalid, recreating socket")
                        # Recreate the socket
                        self.socket_server.close()
                        self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        self.socket_server.bind(self.socket_path)
                        self.socket_server.listen(5)
                        self.socket_server.settimeout(check_interval)
                        logger.info("Socket recreated successfully")
                        continue

                    logger.debug("Waiting for client connection...")
                    client, _ = self.socket_server.accept()
                    logger.info("Client connection accepted")
                    self._handle_client(client)
                except socket.timeout:
                    # This just allows us to check the running flag
                    logger.debug("Socket accept timeout (normal for polling)")
                    continue
        except Exception as e:
            logger.error(f"Error setting up Unix socket server: {e}")
            logger.error(traceback.format_exc())
            self.initialized = False
            # Clean up after failure
            try:
                if hasattr(self, 'socket_server') and self.socket_server:
                    self.socket_server.close()
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except:
                pass
    
    def run_tcp_server(self):
        """Run a TCP server for network communication"""
        logger.info(f"Starting TCP server at {self.tcp_host}:{self.tcp_port}")
        
        # Check stop event frequently to enable responsive termination
        check_interval = 0.1  # Check every 100ms
        last_check_time = time.time()
        
        try:
            # Create socket server
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind((self.tcp_host, self.tcp_port))
            self.socket_server.listen(5)
            self.socket_server.settimeout(check_interval)  # Very short timeout to allow frequent checks
            
            logger.info("TCP server ready")
            
            # Signal that the socket server is ready
            self.socket_server_ready.set()
            
            while self.initialized and not self.stop_event.is_set():
                # Check for termination more frequently
                current_time = time.time()
                if current_time - last_check_time >= check_interval:
                    # Check if we should terminate
                    if self.stop_event.is_set() or not self.initialized:
                        logger.info("Stop event detected in socket server loop, breaking out")
                        break
                    last_check_time = current_time
                
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
        client_addr = "unknown"
        try:
            # Get client address info for logging
            try:
                if hasattr(client, 'getpeername'):
                    client_addr = str(client.getpeername())
                elif hasattr(client, 'getsockname'):
                    client_addr = str(client.getsockname())
            except:
                pass
                
            logger.info(f"New client connection from {client_addr}")
            
            # Set a timeout for receiving data
            client.settimeout(5.0)
            
            # Read data from client
            data = b""
            while True:
                try:
                    chunk = client.recv(MAX_MSG_SIZE)
                    logger.debug(f"Received chunk of size {len(chunk)} bytes from {client_addr}")
                    if not chunk:
                        logger.debug(f"Client {client_addr} closed connection (empty chunk)")
                        break
                    data += chunk
                    
                    # Check if we have a complete JSON object
                    try:
                        _ = json.loads(data.decode('utf-8'))
                        logger.debug(f"Received complete JSON object from {client_addr}")
                        break  # We have a complete JSON object
                    except json.JSONDecodeError:
                        logger.debug(f"Incomplete JSON, continuing to read from {client_addr}")
                        pass  # Continue reading
                except socket.timeout:
                    logger.warning(f"Socket timeout while reading from client {client_addr}")
                    break
                except Exception as e:
                    logger.error(f"Error reading from client {client_addr}: {e}")
                    break
            
            if not data:
                logger.warning(f"No data received from client {client_addr}")
                return
                
            # Parse command
            try:
                command = json.loads(data.decode('utf-8'))
                logger.info(f"Received command from {client_addr}: {command}")
                
                # Queue the command for processing
                self.command_queue.append((client, command))
                logger.debug(f"Command from {client_addr} queued for processing")
                
                # Send acknowledgement
                response = {"status": "queued", "message": "Command accepted"}
                client.send(json.dumps(response).encode('utf-8'))
                logger.debug(f"Sent acknowledgement to {client_addr}: {response}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON data from {client_addr}: {e}")
                logger.error(f"Raw data: {data.decode('utf-8', errors='replace')}")
                response = {"status": "error", "message": f"Invalid JSON data: {str(e)}"}
                client.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
            logger.error(traceback.format_exc())
            try:
                response = {"status": "error", "message": str(e)}
                client.send(json.dumps(response).encode('utf-8'))
            except:
                logger.error(f"Failed to send error response to client {client_addr}")
        finally:
            try:
                client.close()
                logger.debug(f"Closed connection to client {client_addr}")
            except:
                logger.error(f"Error closing client socket for {client_addr}")
    
    def _setup_socket_server(self):
        """Set up the socket server (Unix domain socket or TCP)"""
        logger.info("Setting up socket server")
        
        # Add socket diagnostics
        self._run_socket_diagnostics()
        
        try:
            # Create and start the server thread
            if self.use_tcp:
                logger.info(f"Using TCP socket server on {self.tcp_host}:{self.tcp_port}")
                self.server_thread = threading.Thread(target=self.run_tcp_server)
            else:
                logger.info(f"Using Unix domain socket server at {self.socket_path}")
                
                # Check if the directory for the socket exists
                socket_dir = os.path.dirname(self.socket_path)
                if not os.path.exists(socket_dir):
                    logger.warning(f"Socket directory {socket_dir} does not exist, trying to create it")
                    try:
                        os.makedirs(socket_dir, exist_ok=True)
                        logger.info(f"Created socket directory: {socket_dir}")
                    except Exception as e:
                        logger.error(f"Failed to create socket directory: {e}")
                        return False
                
                # Check if we have write permission to the socket directory
                if not os.access(socket_dir, os.W_OK):
                    logger.error(f"No write permission to socket directory: {socket_dir}")
                    return False
                
                # Check for existing socket file
                if os.path.exists(self.socket_path):
                    logger.warning(f"Socket file already exists at {self.socket_path}, will be removed by server thread")
                    try:
                        # Check if it's actually a socket
                        mode = os.stat(self.socket_path).st_mode
                        is_socket = stat.S_ISSOCK(mode)
                        if not is_socket:
                            logger.error(f"Existing file at {self.socket_path} is not a socket (mode={oct(mode)})")
                    except Exception as e:
                        logger.warning(f"Error checking existing socket file: {e}")
                
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
    
    def _run_socket_diagnostics(self):
        """Run diagnostics on the socket setup to help debug issues"""
        logger.info("Running socket diagnostics...")
        
        # Check if we're using Unix socket or TCP
        if self.use_tcp:
            logger.info(f"Socket type: TCP on {self.tcp_host}:{self.tcp_port}")
            
            # Check if the port is already in use
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind((self.tcp_host, self.tcp_port))
                test_socket.close()
                logger.info(f"TCP port {self.tcp_port} is available")
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    logger.error(f"TCP port {self.tcp_port} is already in use")
                else:
                    logger.error(f"Error checking TCP port: {e}")
        else:
            logger.info(f"Socket type: Unix domain socket at {self.socket_path}")
            
            # Check socket directory
            socket_dir = os.path.dirname(self.socket_path)
            logger.info(f"Socket directory: {socket_dir}")
            
            if os.path.exists(socket_dir):
                logger.info(f"Socket directory exists: {socket_dir}")
                
                # Check directory permissions
                try:
                    dir_stat = os.stat(socket_dir)
                    logger.info(f"Socket directory permissions: {oct(dir_stat.st_mode)}")
                    logger.info(f"Socket directory owner: uid={dir_stat.st_uid}, gid={dir_stat.st_gid}")
                    
                    # Check if we have write permission
                    if os.access(socket_dir, os.W_OK):
                        logger.info(f"We have write permission to socket directory: {socket_dir}")
                    else:
                        logger.error(f"No write permission to socket directory: {socket_dir}")
                        
                        # Check current user and group
                        try:
                            import pwd, grp
                            current_uid = os.getuid()
                            current_gid = os.getgid()
                            user_name = pwd.getpwuid(current_uid).pw_name
                            group_name = grp.getgrgid(current_gid).gr_name
                            logger.info(f"Current user: {user_name} (uid={current_uid})")
                            logger.info(f"Current group: {group_name} (gid={current_gid})")
                        except Exception as e:
                            logger.error(f"Error getting current user/group info: {e}")
                except Exception as e:
                    logger.error(f"Error checking socket directory permissions: {e}")
            else:
                logger.error(f"Socket directory does not exist: {socket_dir}")
                
                # Check if we can create the directory
                try:
                    parent_dir = os.path.dirname(socket_dir)
                    if os.path.exists(parent_dir):
                        if os.access(parent_dir, os.W_OK):
                            logger.info(f"We have permission to create socket directory in: {parent_dir}")
                        else:
                            logger.error(f"No permission to create socket directory in: {parent_dir}")
                    else:
                        logger.error(f"Parent directory does not exist: {parent_dir}")
                except Exception as e:
                    logger.error(f"Error checking parent directory: {e}")
            
            # Check if socket file already exists
            if os.path.exists(self.socket_path):
                logger.info(f"Socket file already exists: {self.socket_path}")
                
                # Check if it's actually a socket
                try:
                    mode = os.stat(self.socket_path).st_mode
                    is_socket = stat.S_ISSOCK(mode)
                    if is_socket:
                        logger.info(f"Existing file is a socket: {self.socket_path}")
                        
                        # Try to connect to the socket to see if it's active
                        try:
                            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                            test_socket.settimeout(1.0)
                            test_socket.connect(self.socket_path)
                            logger.warning(f"Socket is active and accepting connections: {self.socket_path}")
                            test_socket.close()
                        except ConnectionRefusedError:
                            logger.info(f"Socket exists but is not accepting connections: {self.socket_path}")
                        except Exception as e:
                            logger.info(f"Socket exists but connection test failed: {e}")
                    else:
                        logger.error(f"Existing file is NOT a socket (mode={oct(mode)}): {self.socket_path}")
                except Exception as e:
                    logger.error(f"Error checking socket file: {e}")
                
                # Check if we can remove the socket file
                try:
                    if os.access(self.socket_path, os.W_OK):
                        logger.info(f"We have permission to remove socket file: {self.socket_path}")
                    else:
                        logger.error(f"No permission to remove socket file: {self.socket_path}")
                except Exception as e:
                    logger.error(f"Error checking socket file permissions: {e}")
            else:
                logger.info(f"Socket file does not exist: {self.socket_path}")
        
        logger.info("Socket diagnostics completed")

    def _process_commands(self):
        """Process commands from the socket server"""
        logger.info("Starting command processing loop")
        
        # Check if socket_server is initialized
        if self.socket_server is None:
            logger.error("Socket server is not initialized, command processing loop cannot start")
            return
        
        # Start a dedicated thread for the command processing loop so we can
        # return control to the main thread for timeout handling
        def command_processor():
            logger.info("Command processor thread started")
            # Safety timeout to prevent indefinite hanging
            last_activity_time = time.time()
            safety_timeout = int(os.environ.get('EINK_SAFETY_TIMEOUT', str(INACTIVITY_TIMEOUT)))
            
            try:
                while not self.stop_event.is_set() and self.initialized:
                    # Process any queued commands
                    self._process_queued_commands()
                    
                    # Inactivity check
                    if time.time() - last_activity_time > safety_timeout:
                        logger.warning(f"No activity for {safety_timeout} seconds, checking system health")
                        # Just log for now, don't exit
                        last_activity_time = time.time()  # Reset timer
                    
                    # Give the system a short break to prevent CPU hogging
                    time.sleep(0.01)
            
            except Exception as e:
                logger.error(f"Error in command processing loop: {e}")
                logger.error(traceback.format_exc())
                # Mark service as not initialized on error
                self.initialized = False
            finally:
                # Log that we're exiting
                logger.info("Command processor thread exiting")
        
        # Start command processor in a separate thread
        cmd_thread = threading.Thread(target=command_processor, daemon=True)
        cmd_thread.start()
        logger.info("Command processor thread launched, returning to main loop")

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
            
            # Process the command - check both 'action' and 'command' keys for compatibility
            cmd_type = command.get('action', command.get('command', 'unknown'))
            logger.info(f"Command of type {cmd_type} received and being queued")
            
            # Queue the command for processing
            self.command_queue.append((client_socket, command))
            
            # Acknowledge receipt of the command
            self._send_response(client_socket, {
                'status': 'queued',
                'message': f'Command accepted'
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
        
        # Check for both 'action' and 'command' keys for compatibility
        action = command.get('action', command.get('command'))
        
        logger.info(f"Executing command: {action} with args: {command}")
        
        try:
            if action == 'clear':
                logger.info("Executing CLEAR display command")
                self.display.Clear()
                logger.info("Display clear command completed successfully")
                return {
                    'status': 'success',
                    'message': 'Display cleared'
                }
                
            elif action == 'display_text':
                text = command.get('text', '')
                x = command.get('x', 10)
                y = command.get('y', 10)
                font_size = command.get('font_size', 24)
                text_color = command.get('text_color', 'black')
                background_color = command.get('background_color', 'white')
                
                logger.info(f"Executing DISPLAY_TEXT command: '{text}' at ({x},{y}) with font_size={font_size}, text_color={text_color}, bg_color={background_color}")
                
                if hasattr(self.display, 'display_text'):
                    self.display.display_text(text, x, y, font_size, text_color, background_color)
                    logger.info("Display text command completed successfully")
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
                
            elif action == 'display_image':
                # Get image data from command
                image_data_b64 = command.get('image_data')
                image_format = command.get('image_format', 'png')
                
                if not image_data_b64:
                    logger.error("No image data provided in display_image command")
                    return {
                        'status': 'error',
                        'message': 'No image data provided'
                    }
                
                try:
                    # Decode base64 image data
                    logger.debug(f"Decoding base64 image data (length: {len(image_data_b64)})")
                    image_data = base64.b64decode(image_data_b64)
                    logger.debug(f"Decoded image data size: {len(image_data)} bytes")
                    
                    # Convert to PIL Image
                    from PIL import Image, ImageOps
                    import io
                    logger.debug(f"Opening image from bytes with format: {image_format}")
                    
                    # For debugging, save the raw decoded data to a file
                    debug_path = '/tmp/eink_debug_raw.bin'
                    with open(debug_path, 'wb') as f:
                        f.write(image_data)
                    logger.debug(f"Saved raw decoded data to {debug_path}")
                    
                    # Open the image from the byte stream
                    image = Image.open(io.BytesIO(image_data))
                    
                    # Save the image as received to a debug file
                    debug_image_path = f'/tmp/eink_debug_image.{image_format}'
                    image.save(debug_image_path)
                    logger.debug(f"Saved debug image to {debug_image_path}")
                    
                    logger.info(f"Image decoded successfully: format={image.format}, mode={image.mode}, size={image.size}")
                    
                    # Convert to grayscale if needed
                    if image.mode != 'L':
                        logger.info(f"Converting image from {image.mode} to grayscale")
                        image = ImageOps.grayscale(image)
                    
                    # Get the display dimensions
                    display_width = 280  # Default Waveshare 3.7" width
                    display_height = 480 # Default Waveshare 3.7" height
                    
                    # Get actual dimensions if available from the driver
                    if hasattr(self.display, 'width') and hasattr(self.display, 'height'):
                        display_width = self.display.width
                        display_height = self.display.height
                        logger.info(f"Using display dimensions from driver: {display_width}x{display_height}")
                    
                    # Resize image to fit the display if needed
                    if image.size[0] != display_width or image.size[1] != display_height:
                        logger.info(f"Resizing image from {image.size} to {display_width}x{display_height}")
                        image = image.resize((display_width, display_height))
                    
                    # Save the processed image for debug purposes
                    debug_processed_path = '/tmp/eink_debug_processed.png'
                    image.save(debug_processed_path)
                    logger.debug(f"Saved processed image to {debug_processed_path}")
                    
                    # Check if it's time for a full refresh
                    needs_full_refresh = False
                    force_full_refresh = command.get('force_full_refresh', False)
                    
                    if force_full_refresh:
                        needs_full_refresh = True
                        logger.info("Forcing full refresh as requested")
                        self.update_counter = 0
                    elif self.full_refresh_interval > 0:
                        self.update_counter += 1
                        if self.update_counter >= self.full_refresh_interval:
                            needs_full_refresh = True
                            self.update_counter = 0
                            logger.info(f"Performing full refresh after {self.full_refresh_interval} updates")
                    
                    # Perform full refresh if needed
                    if needs_full_refresh and hasattr(self.display, 'Clear') and self.clear_on_full_refresh:
                        logger.info("Clearing display for full refresh")
                        self.display.Clear()
                        # Small delay to allow the clear to complete
                        time.sleep(0.5)
                    
                    logger.info(f"Executing DISPLAY_IMAGE command with image format: {image_format}, size: {image.size}")
                    
                    # Check if display supports display_file method (for file paths)
                    if 'image_path' in command and hasattr(self.display, 'display_file'):
                        image_path = command.get('image_path')
                        resize = command.get('resize', True)
                        logger.info(f"Using display_file method with path: {image_path}, resize: {resize}")
                        self.display.display_file(image_path, resize=resize)
                    # Otherwise use display_image method
                    elif hasattr(self.display, 'display_image'):
                        logger.info("Using display_image method")
                        self.display.display_image(image)
                        
                        # Explicitly call driver refresh to ensure update
                        if hasattr(self.display, 'refresh'):
                            logger.info("Explicitly calling refresh method")
                            self.display.refresh(0 if needs_full_refresh else 1)
                    else:
                        # Fallback for displays without display_image method
                        logger.warning("Display lacks display_image method, using mock implementation")
                        # Mock implementation or return an error
                        return {
                            'status': 'error',
                            'message': 'Display does not support image display'
                        }
                    
                    logger.info("Display image command completed successfully")
                    return {
                        'status': 'success',
                        'message': 'Image displayed successfully',
                        'full_refresh': needs_full_refresh
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing image data: {e}")
                    logger.error(traceback.format_exc())
                    return {
                        'status': 'error',
                        'message': f'Error processing image: {str(e)}'
                    }
                
            elif action == 'sleep':
                logger.info("Executing SLEEP display command")
                self.display.sleep()
                logger.info("Display sleep command completed successfully")
                return {
                    'status': 'success',
                    'message': 'Display put to sleep'
                }
                
            elif action == 'wake':
                logger.info("Executing WAKE display command")
                self.display.init()
                logger.info("Display wake command completed successfully")
                return {
                    'status': 'success',
                    'message': 'Display woken up'
                }
                
            elif action == 'status':
                logger.info("Executing STATUS command")
                return {
                    'status': 'success',
                    'initialized': self.initialized,
                    'mock_mode': self.mock_mode,
                    'display_type': type(self.display).__name__ if self.display else None
                }
            
            elif action == 'debug':
                request_type = command.get('request')
                logger.info(f"Executing DEBUG command: {request_type}")
                
                # Check if we have debug handlers registered
                if hasattr(self, '_debug_command_handlers') and request_type in self._debug_command_handlers:
                    handler = self._debug_command_handlers[request_type]
                    result = handler(self, command)
                    logger.info(f"Debug command completed with result: {result}")
                    return result
                else:
                    return {
                        'status': 'error',
                        'message': f'Unknown debug request: {request_type}'
                    }
                
            else:
                logger.warning(f"Unknown action requested: {action}")
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
        """Clean up resources when the service is terminated."""
        logger.info("Cleaning up EInk service resources")

        # First, handle socket resources if they exist
        try:
            # Handle socket server if it exists
            if hasattr(self, 'socket_server') and self.socket_server:
                logger.info("Closing socket server")
                try:
                    # In case the socket is hanging
                    if hasattr(self.socket_server, 'socket') and self.socket_server.socket:
                        try:
                            self.socket_server.socket.shutdown(socket.SHUT_RDWR)
                        except Exception as e:
                            logger.warning(f"Error shutting down socket: {e}")
                    
                    # Explicit close with additional handling
                    try:
                        fd = self.socket_server.fileno()
                        logger.debug(f"Socket file descriptor: {fd}")
                        self.socket_server.close()
                        logger.info("Socket server closed successfully")
                        try:
                            # Try to close the file descriptor directly
                            os.close(fd)
                            logger.debug(f"Closed file descriptor {fd}")
                        except OSError:
                            pass  # Already closed
                    except Exception as e:
                        logger.error(f"Error closing socket server: {e}")
                except Exception as e:
                    logger.error(f"Error during socket server shutdown: {e}")
            
            # Clean up socket file if it exists and we're using Unix sockets
            if hasattr(self, 'socket_path') and self.socket_path and os.path.exists(self.socket_path):
                logger.info(f"Removing socket file: {self.socket_path}")
                try:
                    # Check if it's actually a socket
                    try:
                        mode = os.stat(self.socket_path).st_mode
                        is_socket = stat.S_ISSOCK(mode)
                        if not is_socket:
                            logger.warning(f"File at {self.socket_path} is not a socket (mode={oct(mode)}), but removing anyway")
                    except Exception as e:
                        logger.warning(f"Error checking socket file type: {e}")
                    
                    # Force remove the file
                    os.unlink(self.socket_path)
                    logger.info("Socket file removed successfully")
                    
                    # Verify removal
                    if os.path.exists(self.socket_path):
                        logger.error(f"Socket file still exists at {self.socket_path} after removal attempt")
                        # Try one more time with force
                        try:
                            os.remove(self.socket_path)
                            logger.info("Socket file removed on second attempt")
                        except Exception as e2:
                            logger.error(f"Failed to remove socket file on second attempt: {e2}")
                except Exception as e:
                    logger.error(f"Error removing socket file: {e}")
        except Exception as e:
            logger.error(f"Error during socket cleanup: {e}")

        # Then, handle display/eink resources
        try:
            # Try to clean up display if it exists
            if hasattr(self, 'display') and self.display:
                logger.info("Cleaning up display resources")
                try:
                    if hasattr(self.display, 'module_exit'):
                        self.display.module_exit()
                        logger.info("Display module_exit called successfully")
                    elif hasattr(self.display, 'close'):
                        self.display.close()
                        logger.info("Display close called successfully")
                    elif hasattr(self.display, 'cleanup'):
                        self.display.cleanup()
                        logger.info("Display cleanup called successfully")
                except Exception as e:
                    logger.error(f"Error cleaning up display resources: {e}")
            
            # Try to clean up eink if it exists and is different from display
            if hasattr(self, 'eink') and self.eink and self.eink != self.display:
                logger.info("Cleaning up eink resources")
                try:
                    if hasattr(self.eink, 'module_exit'):
                        self.eink.module_exit()
                        logger.info("Eink module_exit called successfully")
                    elif hasattr(self.eink, 'close'):
                        self.eink.close()
                        logger.info("Eink close called successfully")
                    elif hasattr(self.eink, 'cleanup'):
                        self.eink.cleanup()
                        logger.info("Eink cleanup called successfully")
                except Exception as e:
                    logger.error(f"Error cleaning up eink resources: {e}")
                
            # Try to clean up RPi.GPIO if it was imported
            try:
                import RPi.GPIO as GPIO
                logger.info("Cleaning up GPIO resources")
                GPIO.cleanup()
                logger.info("GPIO resources cleaned up successfully")
            except (ImportError, RuntimeError) as e:
                logger.debug(f"No GPIO cleanup needed: {e}")
            except Exception as e:
                logger.error(f"Error cleaning up GPIO: {e}")
            
        except Exception as e:
            logger.error(f"Error during display/eink cleanup: {e}")
        
        # Remove PID file if it exists
        try:
            if self.pid_path and os.path.exists(self.pid_path):
                logger.info(f"Removing PID file: {self.pid_path}")
                os.unlink(self.pid_path)
                logger.info("PID file removed successfully")
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
        
        # Mark service as not initialized
        self.initialized = False
        logger.info("EInk service resources cleaned up")

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
                
                # Use the Driver class instead of directly using WaveshareEPD3in7
                try:
                    from devices.eink.drivers.waveshare_3in7 import Driver
                    self.display = Driver()
                    logger.info("Successfully created Driver instance")
                except ImportError:
                    logger.warning("Could not import Driver class, falling back to direct WaveshareEPD3in7 usage")
                    # Directly use the WaveshareEPD3in7 class as fallback
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

    def _handle_refresh(self, operation=None):
        """
        Handle refresh logic for display operations
        """

def run_service(debug_timeout=None):
    """
    Run the EInk service as a standalone process
    
    Args:
        debug_timeout (int, optional): If provided, will exit the service after this many seconds.
                                      Useful for testing and debugging.
    """
    start_time = time.time()
    
    # Convert timeout to int if it's a string
    if debug_timeout is not None and isinstance(debug_timeout, str):
        try:
            debug_timeout = int(debug_timeout)
            logger.info(f"Converted timeout string to int: {debug_timeout}")
        except ValueError:
            logger.error(f"Invalid timeout value: {debug_timeout}, using default")
            debug_timeout = 30
    
    logger.info(f"Debug timeout set to: {debug_timeout}")
    
    # If debug_timeout is set, create a timeout watchdog thread
    if debug_timeout:
        def timeout_watchdog():
            # Give plenty of time for the main loop to handle the timeout
            watchdog_sleep = debug_timeout + 10  # Give a 10-second grace period
            logger.info(f"Timeout watchdog started: will force exit after {watchdog_sleep} seconds")
            time.sleep(watchdog_sleep)
            logger.critical("WATCHDOG TIMEOUT: Forcing process termination!")
            # Force process to exit
            os._exit(1)
            
        # Start watchdog in daemon thread
        watchdog_thread = threading.Thread(target=timeout_watchdog, daemon=True)
        watchdog_thread.start()
        logger.info(f"Started timeout watchdog thread to enforce {debug_timeout}s timeout")
    
    # Create and start service
    try:
        # Set up signal handlers to capture termination signals
        def handle_termination(signum, frame):
            logger.info(f"Received signal {signum}, shutting down EInk service")
            # If service exists, stop it gracefully
            if 'service' in locals() and hasattr(service, 'stop'):
                try:
                    service.stop()
                except Exception as e:
                    logger.error(f"Error stopping service: {e}")
            # Exit the process
            logger.info("Exiting process after signal")
            os._exit(0)
            
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
            # Set an absolute end time for more precise timing
            end_time = start_time + debug_timeout
            logger.info(f"End time set to: {end_time} (current time: {start_time})")
        
        # Add this helper function to test socket connectivity
        def verify_socket_file(socket_path):
            """Verify that the socket file exists and has correct permissions"""
            if not os.path.exists(socket_path):
                logger.error(f"Socket file not found at {socket_path}")
                return False
                
            try:
                # Check socket file permissions
                statinfo = os.stat(socket_path)
                logger.info(f"Socket file stats: mode={oct(statinfo.st_mode)}, uid={statinfo.st_uid}, gid={statinfo.st_gid}")
                
                # Check if file is actually a socket
                is_socket = stat.S_ISSOCK(statinfo.st_mode)
                if not is_socket:
                    logger.error(f"File at {socket_path} is not a socket (mode={oct(statinfo.st_mode)})")
                    return False
                    
                return True
            except Exception as e:
                logger.error(f"Error checking socket file: {e}")
                return False
        
        # Check for socket file but don't actively test connections
        if 'service' in locals() and hasattr(service, 'initialized') and service.initialized:
            socket_path = service.socket_path
            if os.path.exists(socket_path):
                logger.info(f"Socket file exists at {socket_path}")
                socket_ok = verify_socket_file(socket_path)
                if socket_ok:
                    logger.info("Socket file verified, service should be operational")
                else:
                    logger.warning("Socket file exists but verification failed, service may not be fully operational")
            else:
                logger.error(f"Socket file not found at {socket_path}, service is not operational")
        
        # Main service loop - wait for timeout or termination
        if debug_timeout:
            logger.info(f"Entering main loop, will exit after {debug_timeout} seconds")
            try:
                # Wait until the end time or until service is no longer initialized
                while time.time() < end_time and 'service' in locals() and service.initialized:
                    # Sleep for a short time to prevent CPU hogging
                    time.sleep(0.1)
                
                # Log the reason for exiting the loop
                if time.time() >= end_time:
                    logger.info(f"Debug timeout of {debug_timeout} seconds reached, exiting")
                elif not service.initialized:
                    logger.info("Service is no longer initialized, exiting")
                else:
                    logger.info("Exiting main loop for unknown reason")
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received in main loop, shutting down")
        else:
            logger.info("No timeout set, service will run until manually terminated")
            # In non-debug mode, we would normally block here indefinitely
            # But since we're using a separate thread for command processing,
            # we can just return and let the process continue running
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Error running EInk service: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Record exit time
        exit_time = time.time()
        runtime = exit_time - start_time
        
        # Always clean up hardware resources on exit
        if 'service' in locals() and hasattr(service, 'initialized') and service.initialized:
            logger.info("Shutting down EInk service")
            try:
                service.stop()
                logger.info("EInk service stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping service during cleanup: {e}")
        
        # Log the total runtime
        logger.info(f"EInk service has been terminated after running for {int(runtime)}s")
        
        # Force exit to ensure process termination - with a small delay to allow logging
        logger.info("Forcing process exit now")
        time.sleep(0.5)  # Short delay to flush logs
        os._exit(0)


if __name__ == "__main__":
    # Check for command line arguments for debug mode
    debug_timeout = None
    verbose = False
    
    # Process command line arguments
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--debug':
            # If no timeout is specified with --debug, use a default
            if debug_timeout is None:
                debug_timeout = 30
                print(f"Debug mode: Service will exit after {debug_timeout} seconds (default)")
        elif arg.startswith('--timeout='):
            try:
                debug_timeout = int(arg.split('=')[1])
                print(f"Debug mode: Service will exit after {debug_timeout} seconds")
            except (IndexError, ValueError) as e:
                print(f"Invalid timeout value: {arg}, using default of 30 seconds")
                debug_timeout = 30
        elif arg == '--verbose':
            verbose = True
            print("Verbose mode enabled")
            # Set logging level to DEBUG
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
    
    # Log the final timeout value
    if debug_timeout is not None:
        logger.info(f"Debug mode enabled with timeout of {debug_timeout} seconds")
    
    # Run with the timeout if specified
    run_service(debug_timeout) 