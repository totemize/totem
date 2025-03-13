#!/usr/bin/env python3
"""
Install Waveshare e-Paper Driver

This script installs the Waveshare e-Paper driver by:
1. Cloning the official Waveshare e-Paper repository if not already present
2. Creating a symbolic link to make the driver available system-wide
3. Installing required dependencies

Run with sudo for proper permissions:
    sudo python3 install_waveshare_driver.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, check=False):
    """Run a shell command and return the result"""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}", file=sys.stderr)
    if result.returncode != 0 and check:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result

def main():
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root (sudo). Exiting.")
        sys.exit(1)
    
    # Define paths
    home_dir = os.path.expanduser("~")
    waveshare_repo_path = os.path.join(home_dir, "e-Paper")
    python_site_packages = subprocess.check_output("python3 -c 'import site; print(site.getsitepackages()[0])'", 
                                                  shell=True).decode().strip()
    
    # Install required packages
    print("Installing required packages...")
    run_command("apt-get update")
    run_command("apt-get install -y python3-pip python3-pil python3-numpy git")
    
    # Try to install Python packages, but don't fail if they're already installed
    print("Installing Python packages...")
    try:
        run_command("pip3 install RPi.GPIO", check=False)
    except Exception as e:
        print(f"Warning: Could not install RPi.GPIO: {e}")
        print("This is normal if you're using a newer Raspberry Pi with libgpiod.")
    
    try:
        run_command("pip3 install spidev", check=False)
    except Exception as e:
        print(f"Warning: Could not install spidev: {e}")
    
    # Clone Waveshare repository if not exists
    if not os.path.exists(waveshare_repo_path):
        print(f"Cloning Waveshare e-Paper repository to {waveshare_repo_path}...")
        run_command(f"git clone https://github.com/waveshare/e-Paper.git {waveshare_repo_path}")
    else:
        print(f"Waveshare repository already exists at {waveshare_repo_path}")
    
    # Create symbolic link to make the driver available system-wide
    waveshare_epd_path = os.path.join(waveshare_repo_path, "RaspberryPi_JetsonNano/python/lib/waveshare_epd")
    target_path = os.path.join(python_site_packages, "waveshare_epd")
    
    # Remove existing link or directory if exists
    if os.path.exists(target_path) or os.path.islink(target_path):
        print(f"Removing existing {target_path}...")
        if os.path.islink(target_path):
            os.unlink(target_path)
        else:
            shutil.rmtree(target_path)
    
    # Create the symbolic link
    print(f"Creating symbolic link from {waveshare_epd_path} to {target_path}...")
    os.symlink(waveshare_epd_path, target_path)
    
    # Install the package in development mode
    print("Installing the Waveshare driver package...")
    lib_path = os.path.join(waveshare_repo_path, "RaspberryPi_JetsonNano/python/lib")
    try:
        run_command(f"cd {lib_path} && pip3 install -e .", check=False)
    except Exception as e:
        print(f"Warning: Could not install package in development mode: {e}")
        print("This is not critical as we've already created the symbolic link.")
    
    # Create an __init__.py file if it doesn't exist
    init_file = os.path.join(target_path, "__init__.py")
    if not os.path.exists(init_file):
        print(f"Creating {init_file}...")
        with open(init_file, 'w') as f:
            f.write("# Waveshare e-Paper driver package\n")
    
    print("\nWaveshare e-Paper driver installation complete!")
    print("You can now import the driver with: from waveshare_epd import epd3in7")
    
    # Test the installation
    print("\nTesting the installation...")
    test_result = run_command("python3 -c 'try: from waveshare_epd import epd3in7; print(\"Import successful!\"); except Exception as e: print(f\"Import failed: {e}\")'", check=False)
    
    if "Import successful" in test_result.stdout:
        print("\n✅ Installation successful! The waveshare_epd package is now available.")
    else:
        print("\n❌ Installation test failed. Please check the error messages above.")

if __name__ == "__main__":
    main() 