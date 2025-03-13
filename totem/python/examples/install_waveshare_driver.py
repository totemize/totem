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
    
    # Get Python paths
    python_path = run_command("python3 -c 'import sys; print(sys.path)'").stdout
    print(f"Python path: {python_path}")
    
    # Try to get site-packages directory
    try:
        python_site_packages = subprocess.check_output("python3 -c 'import site; print(site.getsitepackages()[0])'", 
                                                    shell=True).decode().strip()
    except:
        # Fallback to a common location
        python_site_packages = "/usr/local/lib/python3.11/dist-packages"
        print(f"Could not determine site-packages directory, using fallback: {python_site_packages}")
    
    # Install required packages
    print("Installing required packages...")
    run_command("apt-get update")
    run_command("apt-get install -y python3-pip python3-pil python3-numpy git python3-rpi.gpio python3-spidev")
    
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
    
    # Create an __init__.py file if it doesn't exist
    init_file = os.path.join(target_path, "__init__.py")
    if not os.path.exists(init_file):
        print(f"Creating {init_file}...")
        with open(init_file, 'w') as f:
            f.write("# Waveshare e-Paper driver package\n")
    
    # Alternative approach: copy the files instead of symlink
    if not os.path.exists(target_path) or not os.listdir(target_path):
        print("Symbolic link failed. Trying to copy files instead...")
        if os.path.islink(target_path):
            os.unlink(target_path)
        elif os.path.exists(target_path):
            shutil.rmtree(target_path)
        
        os.makedirs(target_path, exist_ok=True)
        for item in os.listdir(waveshare_epd_path):
            src = os.path.join(waveshare_epd_path, item)
            dst = os.path.join(target_path, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        
        # Create __init__.py
        with open(os.path.join(target_path, "__init__.py"), 'w') as f:
            f.write("# Waveshare e-Paper driver package\n")
    
    # Add to PYTHONPATH
    print("Adding to PYTHONPATH...")
    pythonpath_file = "/etc/profile.d/waveshare_epd.sh"
    with open(pythonpath_file, 'w') as f:
        f.write(f'export PYTHONPATH="$PYTHONPATH:{os.path.dirname(target_path)}"\n')
    run_command(f"chmod +x {pythonpath_file}")
    
    print("\nWaveshare e-Paper driver installation complete!")
    print("You can now import the driver with: from waveshare_epd import epd3in7")
    
    # Test the installation
    print("\nTesting the installation...")
    test_result = run_command("python3 -c 'import sys; print(sys.path); try: from waveshare_epd import epd3in7; print(\"Import successful!\"); except Exception as e: print(f\"Import failed: {e}\")'", check=False)
    
    if "Import successful" in test_result.stdout:
        print("\n✅ Installation successful! The waveshare_epd package is now available.")
    else:
        print("\n❌ Installation test failed. Please check the error messages above.")
        
        # Try to fix by adding to current PYTHONPATH
        print("\nTrying to fix by adding to current PYTHONPATH...")
        os.environ['PYTHONPATH'] = f"{os.environ.get('PYTHONPATH', '')}:{os.path.dirname(target_path)}"
        test_result = run_command("PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.11/dist-packages python3 -c 'import sys; print(sys.path); try: from waveshare_epd import epd3in7; print(\"Import successful!\"); except Exception as e: print(f\"Import failed: {e}\")'", check=False)
        
        if "Import successful" in test_result.stdout:
            print("\n✅ Fixed! The waveshare_epd package is now available.")
        else:
            print("\n❌ Still failed. Please try to restart your system or manually add the path.")

if __name__ == "__main__":
    main() 