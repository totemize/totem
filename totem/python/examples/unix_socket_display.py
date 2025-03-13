#!/usr/bin/env python3
"""
Unix Socket E-Ink Display Example

This example shows how to communicate with the e-ink display service
using Unix sockets for efficient local IPC.

Usage:
    python unix_socket_display.py [text] [--image=PATH_TO_IMAGE]
"""

import os
import sys
import argparse
import json
import socket
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Constants
DEFAULT_SOCKET_PATH = "/tmp/eink_service.sock"

class UnixSocketDisplayClient:
    """Simple client for communicating with the e-ink display service via Unix socket"""
    
    def __init__(self, socket_path=None):
        """Initialize the client with the socket path"""
        self.socket_path = socket_path or os.environ.get('EINK_SOCKET_PATH', DEFAULT_SOCKET_PATH)
    
    def _send_command(self, command):
        """Send a command to the e-ink service and return the response"""
        # Check if socket file exists
        if not os.path.exists(self.socket_path):
            raise FileNotFoundError(f"Socket file not found: {self.socket_path}. Is the e-ink service running?")
        
        try:
            # Create socket and connect
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5.0)  # 5 second timeout
            sock.connect(self.socket_path)
            
            # Send command as JSON
            command_json = json.dumps(command).encode('utf-8')
            sock.sendall(command_json)
            
            # Receive response
            response_data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            
            # Parse and return response
            response = json.loads(response_data.decode('utf-8'))
            return response
            
        except Exception as e:
            raise RuntimeError(f"Error communicating with e-ink service: {str(e)}")
        finally:
            # Close socket
            if 'sock' in locals():
                sock.close()
    
    def display_text(self, text, font_size=36, x=10, y=10, text_color="black", background_color="white"):
        """Display text on the e-ink display"""
        command = {
            "command": "display_text",
            "text": text,
            "font_size": font_size,
            "x": x,
            "y": y,
            "text_color": text_color,
            "background_color": background_color
        }
        return self._send_command(command)
    
    def display_image(self, image_path):
        """Display an image from a file path"""
        # Read image file
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Encode as base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        command = {
            "command": "display_image",
            "image_data": image_b64,
            "image_format": Path(image_path).suffix[1:].lower()  # Get format from extension (e.g., "png", "jpg")
        }
        return self._send_command(command)
    
    def clear_screen(self):
        """Clear the e-ink display"""
        command = {
            "command": "clear"
        }
        return self._send_command(command)
    
    def sleep(self):
        """Put the e-ink display to sleep"""
        command = {
            "command": "sleep"
        }
        return self._send_command(command)
    
    def wake(self):
        """Wake up the e-ink display"""
        command = {
            "command": "wake"
        }
        return self._send_command(command)
    
    def get_status(self):
        """Get the status of the e-ink display service"""
        command = {
            "command": "status"
        }
        return self._send_command(command)

    def get_debug_info(self):
        """Get debug information from the service"""
        command = {
            "command": "debug",
            "request": "driver_status"
        }
        return self._send_command(command)

def main():
    """Main function to demonstrate Unix socket communication with e-ink display"""
    parser = argparse.ArgumentParser(description='Unix Socket E-Ink Display Example')
    parser.add_argument('text', nargs='?', default="Hello via Unix Socket!", help='Text to display')
    parser.add_argument('--image', type=str, help='Path to an image file to display')
    parser.add_argument('--socket-path', type=str, help='Path to Unix socket file (default: /tmp/eink_service.sock)')
    parser.add_argument('--debug', action='store_true', help='Get debug information')
    parser.add_argument('--text-color', type=str, default="black", help='Text color (default: black)')
    parser.add_argument('--background', type=str, default="white", help='Background color (default: white)')
    parser.add_argument('--font-size', type=int, default=36, help='Font size (default: 36)')
    parser.add_argument('--x', type=int, default=10, help='X position (default: 10)')
    parser.add_argument('--y', type=int, default=10, help='Y position (default: 10)')
    args = parser.parse_args()
    
    try:
        # Create the Unix socket client
        client = UnixSocketDisplayClient(args.socket_path)
        
        # Check if the service is running
        try:
            status = client.get_status()
            print(f"E-ink service status: {status.get('status', 'unknown')}")
        except Exception as e:
            print(f"Error connecting to e-ink service: {e}")
            print("Is the e-ink service running? You can start it with:")
            print("  sudo python -m devices.eink.eink_service")
            return
        
        # If debug mode, get debug info and exit
        if args.debug:
            print("Getting debug information...")
            debug_info = client.get_debug_info()
            print(f"Debug info: {debug_info}")
            return
        
        # Clear the screen first
        print("Clearing the screen...")
        client.clear_screen()
        
        # If an image was provided, display it
        if args.image and os.path.exists(args.image):
            print(f"Displaying image: {args.image}")
            response = client.display_image(args.image)
            print(f"Service response: {response}")
        else:
            # Otherwise, display the text
            print(f"Displaying text: {args.text}")
            response = client.display_text(
                args.text, 
                font_size=args.font_size, 
                x=args.x, 
                y=args.y,
                text_color=args.text_color,
                background_color=args.background
            )
            print(f"Service response: {response}")
        
        print("Display operation completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 