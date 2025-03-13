#!/usr/bin/env python3
"""
Script to install the EInk service as a systemd service
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add the parent directory to the path to import from the project
script_dir = os.path.dirname(os.path.abspath(__file__))
python_dir = os.path.dirname(script_dir)
sys.path.insert(0, python_dir)

# Get the absolute path to the project root
project_root = os.path.abspath(os.path.join(script_dir, ".."))

# Systemd service template
SERVICE_TEMPLATE = """[Unit]
Description=EInk Display Service
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={work_dir}
ExecStart={python_path} {service_script}
Environment="EINK_DISPLAY_TYPE={driver_name}"
Environment="EINK_USE_TCP={use_tcp}"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

def get_username():
    """Get the current username"""
    return os.environ.get("USER", os.environ.get("USERNAME", "pi"))

def get_python_path():
    """Get the path to the Python executable"""
    return sys.executable

def install_service(driver_name=None, use_tcp=False):
    """Install the EInk service as a systemd service"""
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root to install a systemd service.")
        print("Please run with sudo.")
        return False
    
    # Get the current username (the user who ran sudo)
    user = os.environ.get("SUDO_USER", get_username())
    
    # Get the service script path
    service_script = os.path.join(project_root, "devices", "eink", "eink_service.py")
    
    # Fill in the service template
    service_content = SERVICE_TEMPLATE.format(
        user=user,
        work_dir=project_root,
        python_path=get_python_path(),
        service_script=service_script,
        driver_name=driver_name or "",
        use_tcp="1" if use_tcp else "0"
    )
    
    # Write the service file
    service_file = "/etc/systemd/system/eink.service"
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"Service file written to {service_file}")
        
        # Install psutil if not already installed
        try:
            import psutil
        except ImportError:
            print("Installing psutil package...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
        
        # Reload systemd daemon
        subprocess.check_call(["systemctl", "daemon-reload"])
        
        # Enable the service
        subprocess.check_call(["systemctl", "enable", "eink.service"])
        
        # Start the service
        subprocess.check_call(["systemctl", "start", "eink.service"])
        
        print("EInk service installed and started successfully.")
        print("You can check its status with: systemctl status eink.service")
        return True
    
    except Exception as e:
        print(f"Error installing service: {e}")
        return False

def uninstall_service():
    """Uninstall the EInk service"""
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root to uninstall a systemd service.")
        print("Please run with sudo.")
        return False
    
    try:
        # Stop the service if it's running
        try:
            subprocess.check_call(["systemctl", "stop", "eink.service"])
        except:
            pass
        
        # Disable the service
        try:
            subprocess.check_call(["systemctl", "disable", "eink.service"])
        except:
            pass
        
        # Remove the service file
        service_file = "/etc/systemd/system/eink.service"
        if os.path.exists(service_file):
            os.unlink(service_file)
        
        # Reload systemd daemon
        subprocess.check_call(["systemctl", "daemon-reload"])
        
        print("EInk service uninstalled successfully.")
        return True
    
    except Exception as e:
        print(f"Error uninstalling service: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Install or uninstall the EInk service as a systemd service")
    
    # Action
    parser.add_argument("action", choices=["install", "uninstall"], help="Action to perform")
    
    # Driver option
    parser.add_argument("--driver", help="E-ink display driver to use")
    
    # Connection options
    parser.add_argument("--tcp", action="store_true", help="Use TCP instead of Unix socket for service communication")
    
    args = parser.parse_args()
    
    if args.action == "install":
        return 0 if install_service(driver_name=args.driver, use_tcp=args.tcp) else 1
    elif args.action == "uninstall":
        return 0 if uninstall_service() else 1

if __name__ == "__main__":
    sys.exit(main()) 