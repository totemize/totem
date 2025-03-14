#!/usr/bin/env python3
"""
EInk Client - Client library for communicating with the EInk Service

This client allows other processes to communicate with the EInk service,
which maintains exclusive access to the e-ink display hardware.
"""

import os
import sys
import json
import socket
import time
import logging
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image
from typing import Dict, Any, Union, Optional
import stat

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
    logger = logging.getLogger("eink_client")

# Constants
DEFAULT_SOCKET_PATH = "/tmp/eink_service.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 9500

# Timeout values
CONNECT_TIMEOUT = 5.0  # seconds
SEND_TIMEOUT = 10.0    # seconds
RECV_TIMEOUT = 10.0    # seconds

# Max retries
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

class EInkClientError(Exception):
    """Exception for EInk client errors"""
    pass

class EInkClient:
    """
    Client for communicating with the EInk service
    """
    
    def __init__(self, 
                socket_path: Optional[str] = None, 
                tcp_host: Optional[str] = None, 
                tcp_port: Optional[int] = None,
                use_tcp: Optional[bool] = None,
                timeout: float = CONNECT_TIMEOUT):
        """
        Initialize the EInk client
        
        Args:
            socket_path: Path to the Unix socket (for Unix socket mode)
            tcp_host: Hostname for TCP connection (for TCP mode)
            tcp_port: Port for TCP connection (for TCP mode)
            use_tcp: Whether to use TCP instead of Unix socket
            timeout: Connection timeout in seconds
        """
        # Determine socket type
        self.use_tcp = use_tcp if use_tcp is not None else (os.environ.get('EINK_USE_TCP', '0') == '1')
        
        # Set socket path or TCP details
        if self.use_tcp:
            self.tcp_host = tcp_host or os.environ.get('EINK_TCP_HOST', DEFAULT_TCP_HOST)
            self.tcp_port = tcp_port or int(os.environ.get('EINK_TCP_PORT', DEFAULT_TCP_PORT))
        else:
            self.socket_path = socket_path or os.environ.get('EINK_SOCKET_PATH', DEFAULT_SOCKET_PATH)
        
        self.timeout = timeout
    
    def _connect(self) -> socket.socket:
        """
        Connect to the EInk service
        
        Returns:
            socket.socket: Connected socket
            
        Raises:
            EInkClientError: If connection fails
        """
        for attempt in range(MAX_RETRIES):
            try:
                if self.use_tcp:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.timeout)
                    sock.connect((self.tcp_host, self.tcp_port))
                else:
                    # Check if socket file exists
                    if not os.path.exists(self.socket_path):
                        raise EInkClientError(f"Socket file not found: {self.socket_path}")
                    
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(self.timeout)
                    sock.connect(self.socket_path)
                
                return sock
                
            except (socket.error, OSError) as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise EInkClientError(f"Failed to connect to EInk service: {e}")
    
    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Run diagnostics on the connection to the EInk service
        
        Returns:
            dict: Diagnostic information
        """
        logger.info("Running EInkClient diagnostics...")
        diagnostics = {
            "timestamp": time.time(),
            "use_tcp": self.use_tcp,
            "socket_path": self.socket_path if not self.use_tcp else None,
            "tcp_host": self.tcp_host if self.use_tcp else None,
            "tcp_port": self.tcp_port if self.use_tcp else None,
            "timeout": self.timeout,
            "socket_exists": False,
            "socket_permissions": None,
            "socket_is_socket": False,
            "connection_successful": False,
            "service_status": None,
            "errors": []
        }
        
        try:
            # Check if socket file exists (for Unix socket)
            if not self.use_tcp:
                if os.path.exists(self.socket_path):
                    diagnostics["socket_exists"] = True
                    logger.info(f"Socket file exists: {self.socket_path}")
                    
                    # Check socket file permissions
                    try:
                        stat_info = os.stat(self.socket_path)
                        mode = stat_info.st_mode
                        diagnostics["socket_permissions"] = {
                            "mode": oct(mode),
                            "uid": stat_info.st_uid,
                            "gid": stat_info.st_gid
                        }
                        logger.info(f"Socket permissions: mode={oct(mode)}, uid={stat_info.st_uid}, gid={stat_info.st_gid}")
                        
                        # Check if it's actually a socket
                        is_socket = stat.S_ISSOCK(mode)
                        diagnostics["socket_is_socket"] = is_socket
                        if is_socket:
                            logger.info(f"File is a socket: {self.socket_path}")
                        else:
                            logger.error(f"File is NOT a socket: {self.socket_path}")
                            diagnostics["errors"].append(f"File exists but is not a socket: {self.socket_path}")
                    except Exception as e:
                        logger.error(f"Error checking socket file: {e}")
                        diagnostics["errors"].append(f"Error checking socket file: {str(e)}")
                else:
                    logger.error(f"Socket file not found: {self.socket_path}")
                    diagnostics["errors"].append(f"Socket file not found: {self.socket_path}")
                    
                    # Check socket directory
                    socket_dir = os.path.dirname(self.socket_path)
                    if os.path.exists(socket_dir):
                        logger.info(f"Socket directory exists: {socket_dir}")
                        
                        # Check directory permissions
                        try:
                            dir_stat = os.stat(socket_dir)
                            logger.info(f"Socket directory permissions: {oct(dir_stat.st_mode)}")
                            logger.info(f"Socket directory owner: uid={dir_stat.st_uid}, gid={dir_stat.st_gid}")
                        except Exception as e:
                            logger.error(f"Error checking socket directory: {e}")
                            diagnostics["errors"].append(f"Error checking socket directory: {str(e)}")
                    else:
                        logger.error(f"Socket directory does not exist: {socket_dir}")
                        diagnostics["errors"].append(f"Socket directory does not exist: {socket_dir}")
            
            # Try to connect to the service
            try:
                sock = self._connect()
                diagnostics["connection_successful"] = True
                logger.info("Successfully connected to EInk service")
                
                # Try to get service status
                try:
                    status = self.get_status()
                    diagnostics["service_status"] = status
                    logger.info(f"Service status: {status}")
                except Exception as e:
                    logger.error(f"Error getting service status: {e}")
                    diagnostics["errors"].append(f"Error getting service status: {str(e)}")
                
                sock.close()
            except EInkClientError as e:
                logger.error(f"Connection failed: {e}")
                diagnostics["errors"].append(f"Connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error during diagnostics: {e}")
            diagnostics["errors"].append(f"Error during diagnostics: {str(e)}")
        
        logger.info("EInkClient diagnostics completed")
        return diagnostics
    
    def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a command to the EInk service and get the response
        
        Args:
            command: Command dictionary to send
            
        Returns:
            dict: Response from the service
            
        Raises:
            EInkClientError: If communication fails
        """
        sock = None
        try:
            # Connect to the service
            sock = self._connect()
            
            # Set timeout for sending/receiving
            sock.settimeout(SEND_TIMEOUT)
            
            # Serialize and send the command
            message = json.dumps(command).encode('utf-8')
            sock.sendall(message)
            
            # Set timeout for receiving
            sock.settimeout(RECV_TIMEOUT)
            
            # Receive response
            response_data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # Check if response is complete (this is a simple approach)
                try:
                    json.loads(response_data.decode('utf-8'))
                    break  # If we can parse it, we have a complete response
                except json.JSONDecodeError:
                    # Incomplete JSON, continue receiving
                    continue
            
            # Parse response
            response = json.loads(response_data.decode('utf-8'))
            return response
            
        except (socket.error, OSError, json.JSONDecodeError) as e:
            raise EInkClientError(f"Communication error: {e}")
        finally:
            # Clean up
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    def clear_screen(self) -> Dict[str, Any]:
        """
        Clear the e-ink display
        
        Returns:
            dict: Response from the service
        """
        command = {'action': 'clear'}
        return self._send_command(command)
    
    def display_text(self, text: str, x: int = 10, y: int = 10, font_size: int = 24, font: Optional[str] = None, text_color: str = "black", background_color: str = "white") -> Dict[str, Any]:
        """
        Display text on the e-ink display
        
        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate
            font_size: Font size
            font: Path to font file (optional)
            text_color: Color of the text (default: "black")
            background_color: Background color (default: "white")
            
        Returns:
            dict: Response from the service
        """
        command = {
            'action': 'display_text',
            'text': text,
            'x': x,
            'y': y,
            'font_size': font_size,
            'text_color': text_color,
            'background_color': background_color
        }
        
        # Add font if provided
        if font:
            command['font'] = font
            
        return self._send_command(command)
    
    def display_image(self, image=None, image_path=None, force_full_refresh=False) -> Dict[str, Any]:
        """
        Display an image on the e-ink display
        
        Args:
            image: PIL Image object (optional)
            image_path: Path to image file (optional)
            force_full_refresh: Force a full refresh regardless of the counter (optional)
            
        Returns:
            dict: Response from the service
            
        Note:
            Either image or image_path must be provided, but not both.
        """
        if image is None and image_path is None:
            raise ValueError("Either image or image_path must be provided")
        
        if image is not None and image_path is not None:
            raise ValueError("Only one of image or image_path should be provided")
        
        command = {'action': 'display_image'}
        
        # Add force_full_refresh flag if specified
        if force_full_refresh:
            command['force_full_refresh'] = True
        
        if image_path:
            # Read image file
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Encode as base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Add to command
            command['image_data'] = image_b64
            command['image_format'] = Path(image_path).suffix[1:].lower()  # Get format from extension (e.g., "png", "jpg")
        else:
            # Convert PIL Image to bytes
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            
            # Encode as base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Add to command
            command['image_data'] = image_b64
            command['image_format'] = 'png'
        
        return self._send_command(command)
    
    def sleep(self) -> Dict[str, Any]:
        """
        Put the display to sleep
        
        Returns:
            dict: Response from the service
        """
        command = {'action': 'sleep'}
        return self._send_command(command)
    
    def wake(self) -> Dict[str, Any]:
        """
        Wake up the display
        
        Returns:
            dict: Response from the service
        """
        command = {'action': 'wake'}
        return self._send_command(command)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the service
        
        Returns:
            dict: Status information
        """
        command = {'action': 'status'}
        return self._send_command(command)


# Simple command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="EInk Client - Send commands to the EInk service")
    
    # Connection options
    conn_group = parser.add_argument_group("Connection options")
    conn_group.add_argument("--tcp", action="store_true", help="Use TCP instead of Unix socket")
    conn_group.add_argument("--socket-path", help="Path to Unix socket file")
    conn_group.add_argument("--host", help="TCP host address")
    conn_group.add_argument("--port", type=int, help="TCP port")
    
    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear the display")
    
    # Text command
    text_parser = subparsers.add_parser("text", help="Display text")
    text_parser.add_argument("text", help="Text to display")
    text_parser.add_argument("--font-size", type=int, default=24, help="Font size")
    text_parser.add_argument("--x", type=int, default=10, help="X coordinate")
    text_parser.add_argument("--y", type=int, default=10, help="Y coordinate")
    text_parser.add_argument("--font", help="Path to font file")
    
    # Image command
    image_parser = subparsers.add_parser("image", help="Display image")
    image_parser.add_argument("image_path", help="Path to image file")
    
    # Sleep command
    sleep_parser = subparsers.add_parser("sleep", help="Put the display to sleep")
    
    # Wake command
    wake_parser = subparsers.add_parser("wake", help="Wake up the display")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get the status of the EInk service")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create client
    client = EInkClient(
        socket_path=args.socket_path,
        tcp_host=args.host,
        tcp_port=args.port,
        use_tcp=args.tcp
    )
    
    # Execute command
    if args.command == "clear":
        result = client.clear_screen()
    elif args.command == "text":
        result = client.display_text(
            args.text,
            font_size=args.font_size,
            x=args.x,
            y=args.y,
            font=args.font
        )
    elif args.command == "image":
        result = client.display_image(image_path=args.image_path)
    elif args.command == "sleep":
        result = client.sleep()
    elif args.command == "wake":
        result = client.wake()
    elif args.command == "status":
        result = client.get_status()
    else:
        parser.print_help()
        sys.exit(1)
    
    # Print result
    if result:
        print(json.dumps(result, indent=2)) 