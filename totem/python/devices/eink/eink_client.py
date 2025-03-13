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
import logging
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

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


class EInkClient:
    """
    Client for communicating with the EInk service
    """
    
    def __init__(self, use_unix_socket=True, socket_path=None, tcp_host=None, tcp_port=None):
        """
        Initialize the EInk client
        
        Args:
            use_unix_socket: Whether to use Unix socket (True) or TCP (False)
            socket_path: Path to Unix socket file (default: /tmp/eink_service.sock)
            tcp_host: TCP host address (default: 127.0.0.1)
            tcp_port: TCP port (default: 9500)
        """
        # Connection settings
        self.use_unix_socket = use_unix_socket
        self.socket_path = socket_path or DEFAULT_SOCKET_PATH
        self.tcp_host = tcp_host or DEFAULT_TCP_HOST
        self.tcp_port = tcp_port or DEFAULT_TCP_PORT
        
        # Override connection settings from environment if available
        if os.environ.get('EINK_USE_TCP', '0') == '1':
            self.use_unix_socket = False
        
        if os.environ.get('EINK_SOCKET_PATH'):
            self.socket_path = os.environ.get('EINK_SOCKET_PATH')
            
        if os.environ.get('EINK_TCP_HOST'):
            self.tcp_host = os.environ.get('EINK_TCP_HOST')
            
        if os.environ.get('EINK_TCP_PORT'):
            try:
                self.tcp_port = int(os.environ.get('EINK_TCP_PORT'))
            except ValueError:
                pass
    
    def _send_command(self, command):
        """
        Send a command to the EInk service
        
        Args:
            command: Command dictionary to send
            
        Returns:
            Dictionary containing the response from the server
        """
        # Create socket based on connection type
        if self.use_unix_socket:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Connect to the server
            if self.use_unix_socket:
                sock.connect(self.socket_path)
            else:
                sock.connect((self.tcp_host, self.tcp_port))
            
            # Send the command
            command_json = json.dumps(command).encode('utf-8')
            sock.sendall(command_json)
            
            # Read the response
            response_data = b""
            sock.settimeout(5.0)
            
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # Check if we have a complete JSON object
                try:
                    _ = json.loads(response_data.decode('utf-8'))
                    break  # We have a complete JSON object
                except:
                    pass  # Continue reading
            
            # Parse and return the response
            if response_data:
                try:
                    return json.loads(response_data.decode('utf-8'))
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response: {response_data.decode('utf-8')}")
                    return {"status": "error", "message": "Invalid JSON response"}
            else:
                return {"status": "error", "message": "No response from server"}
                
        except ConnectionRefusedError:
            logger.error("Connection refused. Is the EInk service running?")
            return {"status": "error", "message": "Connection refused. Is the EInk service running?"}
        except FileNotFoundError:
            logger.error(f"Socket file not found: {self.socket_path}")
            return {"status": "error", "message": f"Socket file not found: {self.socket_path}"}
        except socket.timeout:
            logger.error("Connection timed out")
            return {"status": "error", "message": "Connection timed out"}
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            sock.close()
    
    def clear_display(self):
        """Clear the e-ink display"""
        command = {"action": "clear"}
        return self._send_command(command)
    
    def display_text(self, text, font_size=24, x=10, y=10, font=None):
        """
        Display text on the e-ink display
        
        Args:
            text: Text to display
            font_size: Font size in pixels
            x: X coordinate
            y: Y coordinate
            font: Path to font file (optional)
        """
        command = {
            "action": "display_text",
            "text": text,
            "font_size": font_size,
            "x": x,
            "y": y
        }
        
        if font:
            command["font"] = font
            
        return self._send_command(command)
    
    def display_image(self, image_path=None, image=None):
        """
        Display an image on the e-ink display
        
        Args:
            image_path: Path to image file (optional)
            image: PIL Image object (optional)
            
        Note: Either image_path or image must be provided
        """
        if not image_path and not image:
            logger.error("Either image_path or image must be provided")
            return {"status": "error", "message": "Either image_path or image must be provided"}
        
        command = {"action": "display_image"}
        
        if image_path:
            # Use path-based image display
            command["image_path"] = str(image_path)
        elif image:
            # Convert PIL image to base64
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            command["image_data"] = image_data
            
        return self._send_command(command)
    
    def sleep_display(self):
        """Put the display to sleep"""
        command = {"action": "sleep"}
        return self._send_command(command)
    
    def wake_display(self):
        """Wake up the display"""
        command = {"action": "wake"}
        return self._send_command(command)
    
    def get_status(self):
        """Get the status of the EInk service"""
        command = {"action": "status"}
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
        use_unix_socket=not args.tcp,
        socket_path=args.socket_path,
        tcp_host=args.host,
        tcp_port=args.port
    )
    
    # Execute command
    if args.command == "clear":
        result = client.clear_display()
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
        result = client.sleep_display()
    elif args.command == "wake":
        result = client.wake_display()
    elif args.command == "status":
        result = client.get_status()
    else:
        parser.print_help()
        sys.exit(1)
    
    # Print result
    if result:
        print(json.dumps(result, indent=2)) 