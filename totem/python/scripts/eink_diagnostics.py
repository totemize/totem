#!/usr/bin/env python3
"""
E-Ink Display Diagnostics Script
This script diagnoses common issues with E-Ink displays and helps resolve them.
"""

import os
import sys
import time
import subprocess
import traceback
import platform
import importlib.util
from pathlib import Path

# Add the parent directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, parent_dir)

# Set up logging
try:
    from utils.logger import logger, setup_logger
    setup_logger(level=10)  # Debug level
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("eink_diagnostics")

class EInkDiagnostics:
    """Class to diagnose E-Ink display issues"""
    
    def __init__(self):
        self.is_raspberry_pi = self._check_is_raspberry_pi()
        self.is_raspberry_pi_5 = self._check_is_raspberry_pi_5()
        self.python_version = sys.version
        self.os_info = platform.platform()
        
        # Initialize test results
        self.results = {
            "system": {
                "is_raspberry_pi": self.is_raspberry_pi,
                "is_raspberry_pi_5": self.is_raspberry_pi_5,
                "python_version": self.python_version,
                "os_info": self.os_info
            },
            "modules": {},
            "hardware": {},
            "configuration": {},
            "permissions": {}
        }
    
    def _check_is_raspberry_pi(self):
        """Check if running on a Raspberry Pi"""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                return 'Raspberry Pi' in model
        except:
            return False
    
    def _check_is_raspberry_pi_5(self):
        """Check if running on a Raspberry Pi 5"""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                return 'Raspberry Pi 5' in model
        except:
            return False
    
    def check_python_modules(self):
        """Check for required Python modules"""
        modules = ["spidev", "gpiod", "numpy", "PIL"]
        
        for module in modules:
            try:
                if module == "PIL":
                    # Special case for PIL which is imported as 'from PIL import Image'
                    from PIL import Image
                    version = getattr(Image, "__version__", "unknown")
                else:
                    # Try to import the module
                    imported_module = importlib.import_module(module)
                    version = getattr(imported_module, "__version__", "unknown")
                
                self.results["modules"][module] = {
                    "installed": True,
                    "version": version
                }
                print(f"✅ {module} is installed (version: {version})")
            except ImportError:
                self.results["modules"][module] = {
                    "installed": False,
                    "error": "Module not found"
                }
                print(f"❌ {module} is not installed")
            except Exception as e:
                self.results["modules"][module] = {
                    "installed": False,
                    "error": str(e)
                }
                print(f"⚠️ Error checking {module}: {e}")
    
    def check_hardware_devices(self):
        """Check for hardware devices like SPI and GPIO"""
        # Check SPI devices
        self.results["hardware"]["spi"] = {"available": False, "devices": []}
        
        try:
            spi_devices = [f for f in os.listdir('/dev') if f.startswith('spi')]
            if spi_devices:
                print(f"✅ SPI devices found: {', '.join(spi_devices)}")
                self.results["hardware"]["spi"]["available"] = True
                self.results["hardware"]["spi"]["devices"] = spi_devices
            else:
                print("❌ No SPI devices found in /dev")
        except Exception as e:
            print(f"⚠️ Error checking SPI devices: {e}")
            self.results["hardware"]["spi"]["error"] = str(e)
        
        # Check GPIO devices
        self.results["hardware"]["gpio"] = {"available": False, "devices": []}
        
        try:
            gpio_devices = [f for f in os.listdir('/dev') if f.startswith('gpio')]
            if gpio_devices:
                print(f"✅ GPIO devices found: {', '.join(gpio_devices)}")
                self.results["hardware"]["gpio"]["available"] = True
                self.results["hardware"]["gpio"]["devices"] = gpio_devices
            else:
                print("❌ No GPIO devices found in /dev")
        except Exception as e:
            print(f"⚠️ Error checking GPIO devices: {e}")
            self.results["hardware"]["gpio"]["error"] = str(e)
    
    def check_system_configuration(self):
        """Check system configuration for SPI and I2C"""
        # Check if SPI is enabled in /boot/config.txt
        self.results["configuration"]["spi_enabled"] = False
        self.results["configuration"]["i2c_enabled"] = False
        
        try:
            if os.path.exists('/boot/config.txt'):
                with open('/boot/config.txt', 'r') as f:
                    config = f.read()
                    
                    if 'dtparam=spi=on' in config and not '#dtparam=spi=on' in config:
                        print("✅ SPI is enabled in /boot/config.txt")
                        self.results["configuration"]["spi_enabled"] = True
                    else:
                        print("❌ SPI is not enabled in /boot/config.txt")
                    
                    if 'dtparam=i2c_arm=on' in config and not '#dtparam=i2c_arm=on' in config:
                        print("✅ I2C is enabled in /boot/config.txt")
                        self.results["configuration"]["i2c_enabled"] = True
                    else:
                        print("❌ I2C is not enabled in /boot/config.txt")
            else:
                print("⚠️ /boot/config.txt not found (not running on Raspberry Pi?)")
        except Exception as e:
            print(f"⚠️ Error checking system configuration: {e}")
            self.results["configuration"]["error"] = str(e)
        
        # Check SPI kernel modules
        try:
            spi_modules = subprocess.check_output("lsmod | grep spi", shell=True).decode()
            if spi_modules:
                print(f"✅ SPI kernel modules loaded: {spi_modules.strip()}")
                self.results["configuration"]["spi_modules"] = spi_modules.strip()
            else:
                print("❌ No SPI kernel modules loaded")
                self.results["configuration"]["spi_modules"] = None
        except subprocess.CalledProcessError:
            print("❌ No SPI kernel modules loaded")
            self.results["configuration"]["spi_modules"] = None
        except Exception as e:
            print(f"⚠️ Error checking SPI kernel modules: {e}")
            self.results["configuration"]["spi_modules_error"] = str(e)
    
    def check_permissions(self):
        """Check permissions for SPI and GPIO devices"""
        # Check SPI permissions
        self.results["permissions"]["spidev"] = {"readable": False, "writable": False}
        self.results["permissions"]["gpiochip"] = {"readable": False, "writable": False}
        self.results["permissions"]["user_in_gpio_group"] = False
        
        try:
            # Check if user is in gpio group
            groups = subprocess.check_output(["groups"]).decode().strip().split()
            if 'gpio' in groups:
                print("✅ User is in the gpio group")
                self.results["permissions"]["user_in_gpio_group"] = True
            else:
                print("❌ User is not in the gpio group")
            
            # Check SPI device permissions
            spi_device = '/dev/spidev0.0'
            if os.path.exists(spi_device):
                spi_stat = os.stat(spi_device)
                spi_perms = format(spi_stat.st_mode & 0o777, 'o')
                print(f"SPI device permissions: {spi_perms}")
                
                # Check if readable by current user
                if os.access(spi_device, os.R_OK):
                    print("✅ SPI device is readable")
                    self.results["permissions"]["spidev"]["readable"] = True
                else:
                    print("❌ SPI device is not readable")
                
                # Check if writable by current user
                if os.access(spi_device, os.W_OK):
                    print("✅ SPI device is writable")
                    self.results["permissions"]["spidev"]["writable"] = True
                else:
                    print("❌ SPI device is not writable")
            else:
                print("❌ SPI device not found")
            
            # Check GPIO device permissions
            gpio_device = '/dev/gpiochip0'
            if os.path.exists(gpio_device):
                gpio_stat = os.stat(gpio_device)
                gpio_perms = format(gpio_stat.st_mode & 0o777, 'o')
                print(f"GPIO device permissions: {gpio_perms}")
                
                # Check if readable by current user
                if os.access(gpio_device, os.R_OK):
                    print("✅ GPIO device is readable")
                    self.results["permissions"]["gpiochip"]["readable"] = True
                else:
                    print("❌ GPIO device is not readable")
                
                # Check if writable by current user
                if os.access(gpio_device, os.W_OK):
                    print("✅ GPIO device is writable")
                    self.results["permissions"]["gpiochip"]["writable"] = True
                else:
                    print("❌ GPIO device is not writable")
            else:
                print("❌ GPIO device not found")
        except Exception as e:
            print(f"⚠️ Error checking permissions: {e}")
            self.results["permissions"]["error"] = str(e)
    
    def attempt_driver_imports(self):
        """Attempt to import all E-Ink drivers to check for issues"""
        print("\nAttempting to import E-Ink drivers...")
        drivers = [
            "waveshare_2in13",
            "waveshare_2in13_pi5",
            "waveshare_3in7",
            "waveshare_3in7_pi5"
        ]
        
        self.results["drivers"] = {}
        
        for driver in drivers:
            try:
                print(f"Importing {driver}...")
                module_path = f"devices.eink.drivers.{driver}"
                spec = importlib.util.find_spec(module_path)
                
                if spec is None:
                    print(f"❌ Module {module_path} not found")
                    self.results["drivers"][driver] = {
                        "found": False,
                        "importable": False,
                        "error": "Module not found"
                    }
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check if Driver class is available
                if hasattr(module, 'Driver'):
                    print(f"✅ Successfully imported {driver}")
                    self.results["drivers"][driver] = {
                        "found": True,
                        "importable": True
                    }
                else:
                    print(f"⚠️ Driver class not found in {driver}")
                    self.results["drivers"][driver] = {
                        "found": True,
                        "importable": False,
                        "error": "Driver class not found"
                    }
            except Exception as e:
                print(f"❌ Error importing {driver}: {e}")
                self.results["drivers"][driver] = {
                    "found": True,
                    "importable": False,
                    "error": str(e)
                }
    
    def generate_fix_suggestions(self):
        """Generate suggestions to fix identified issues"""
        print("\n=== Suggested Fixes ===")
        
        suggestions = []
        
        # Check for module issues
        for module, info in self.results["modules"].items():
            if not info.get("installed", False):
                if module == "spidev":
                    suggestions.append(f"Install {module} with: sudo pip3 install {module}")
                elif module == "gpiod":
                    suggestions.append(f"Install {module} with: sudo apt install python3-{module}")
                else:
                    suggestions.append(f"Install {module} with: sudo pip3 install {module}")
        
        # Check hardware issues
        if not self.results["hardware"].get("spi", {}).get("available", False):
            suggestions.append("Enable SPI by running: sudo raspi-config")
            suggestions.append("Then navigate to: Interface Options > SPI > Yes")
        
        # Check configuration issues
        if not self.results["configuration"].get("spi_enabled", False):
            suggestions.append("Add 'dtparam=spi=on' to /boot/config.txt")
            suggestions.append("Run: sudo echo 'dtparam=spi=on' >> /boot/config.txt")
        
        # Check permission issues
        if not self.results["permissions"].get("user_in_gpio_group", False):
            suggestions.append("Add user to gpio group with: sudo usermod -a -G gpio $USER")
            suggestions.append("You'll need to log out and log back in for this to take effect")
        
        if not self.results["permissions"].get("spidev", {}).get("readable", False) or \
           not self.results["permissions"].get("spidev", {}).get("writable", False):
            suggestions.append("Fix SPI permissions with: sudo chmod 666 /dev/spidev0.*")
        
        if not self.results["permissions"].get("gpiochip", {}).get("readable", False) or \
           not self.results["permissions"].get("gpiochip", {}).get("writable", False):
            suggestions.append("Fix GPIO permissions with: sudo chmod 666 /dev/gpiochip0")
        
        # Check if any driver imports failed
        driver_errors = False
        for driver, info in self.results.get("drivers", {}).items():
            if not info.get("importable", False):
                driver_errors = True
        
        if driver_errors:
            suggestions.append("Run the fix dependencies script: sudo ./fix_eink_dependencies.sh")
        
        # Display all suggestions
        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion}")
        else:
            print("No issues found that need fixing!")
        
        # Reboot recommendation
        if suggestions:
            print("\nAfter making these changes, it's recommended to reboot your system:")
            print("sudo reboot")
    
    def run_diagnostics(self):
        """Run all diagnostic checks"""
        print("=== E-Ink Display Diagnostics ===")
        print(f"System: {self.os_info}")
        print(f"Python: {self.python_version}")
        print(f"Raspberry Pi: {'Yes' if self.is_raspberry_pi else 'No'}")
        print(f"Raspberry Pi 5: {'Yes' if self.is_raspberry_pi_5 else 'No'}")
        print("\n=== Checking Python Modules ===")
        self.check_python_modules()
        print("\n=== Checking Hardware Devices ===")
        self.check_hardware_devices()
        print("\n=== Checking System Configuration ===")
        self.check_system_configuration()
        print("\n=== Checking Permissions ===")
        self.check_permissions()
        self.attempt_driver_imports()
        self.generate_fix_suggestions()

def main():
    """Main function to run the diagnostics"""
    diagnostics = EInkDiagnostics()
    try:
        diagnostics.run_diagnostics()
        print("\nDiagnostics completed successfully!")
        return 0
    except Exception as e:
        print(f"Error running diagnostics: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 