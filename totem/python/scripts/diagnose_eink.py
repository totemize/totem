#!/usr/bin/env python3
"""
E-Ink Display Diagnostic Script
This script diagnoses issues with the E-Ink display, particularly the spidev module error.
"""

import os
import sys
import importlib
import subprocess
import traceback

# Configure path to include the totem modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, project_root)

try:
    from utils.logger import logger, setup_logger
except ImportError:
    print("Could not import logger module. Using basic logging.")
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("eink_diagnostic")

def check_system_info():
    """Check system information to help with diagnosis"""
    print("\n=== SYSTEM INFORMATION ===")
    
    # Check OS
    print(f"Python version: {sys.version}")
    
    try:
        os_info = subprocess.check_output(["uname", "-a"]).decode().strip()
        print(f"OS Info: {os_info}")
    except:
        print("Could not determine OS information")
    
    # Check if running on Raspberry Pi
    is_raspberry_pi = False
    if os.path.exists('/proc/cpuinfo'):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                if 'Raspberry Pi' in cpuinfo:
                    is_raspberry_pi = True
                    model = [line for line in cpuinfo.split('\n') if 'Model' in line]
                    if model:
                        print(f"Raspberry Pi Model: {model[0].split(':')[1].strip()}")
                    else:
                        print("Detected Raspberry Pi (model unknown)")
        except:
            print("Could not read /proc/cpuinfo")
    
    if not is_raspberry_pi:
        print("WARNING: Not running on a Raspberry Pi. E-Ink hardware tests will likely fail.")

def check_required_modules():
    """Check if the required Python modules are installed"""
    print("\n=== PYTHON MODULE CHECK ===")
    
    required_modules = [
        "spidev",
        "gpiod",
        "numpy",
        "PIL", # Pillow
    ]
    
    all_modules_installed = True
    
    for module in required_modules:
        try:
            if module == "PIL":
                importlib.import_module("PIL.Image")
                print(f"✅ {module} module is installed")
            else:
                importlib.import_module(module)
                print(f"✅ {module} module is installed")
        except ImportError as e:
            print(f"❌ {module} module is NOT installed: {e}")
            all_modules_installed = False
    
    return all_modules_installed

def check_system_packages():
    """Check if required system packages are installed"""
    print("\n=== SYSTEM PACKAGE CHECK ===")
    
    if not os.path.exists('/usr/bin/dpkg'):
        print("System package check skipped (not on Debian/Ubuntu)")
        return
    
    required_packages = [
        "python3-pip",
        "python3-dev",
        "python3-setuptools",
        "python3-wheel",
        "python3-gpiod",
        "libgpiod-dev",
        "i2c-tools",
        "spi-tools",
    ]
    
    for package in required_packages:
        try:
            result = subprocess.run(
                ["dpkg", "-s", package], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                print(f"✅ {package} is installed")
            else:
                print(f"❌ {package} is NOT installed")
        except:
            print(f"Could not check if {package} is installed")

def check_spi_interface():
    """Check if the SPI interface is enabled and accessible"""
    print("\n=== SPI INTERFACE CHECK ===")
    
    # Check if SPI module is loaded
    try:
        lsmod_output = subprocess.check_output(["lsmod"]).decode()
        if "spi" in lsmod_output:
            print("✅ SPI kernel module is loaded")
        else:
            print("❌ SPI kernel module is NOT loaded")
    except:
        print("Could not check if SPI kernel module is loaded")
    
    # Check if SPI is enabled in config
    if os.path.exists('/boot/config.txt'):
        try:
            with open('/boot/config.txt', 'r') as f:
                config = f.read()
                if 'dtparam=spi=on' in config and not '#dtparam=spi=on' in config:
                    print("✅ SPI is enabled in /boot/config.txt")
                else:
                    print("❌ SPI is NOT enabled in /boot/config.txt")
        except:
            print("Could not read /boot/config.txt")
    
    # Check if SPI device exists
    if os.path.exists('/dev/spidev0.0'):
        print("✅ SPI device /dev/spidev0.0 exists")
        try:
            permissions = oct(os.stat('/dev/spidev0.0').st_mode)[-3:]
            print(f"   Permissions: {permissions}")
            if int(permissions[2]) >= 4:  # Check if world-readable
                print("✅ SPI device is readable by current user")
            else:
                print("❌ SPI device is NOT readable by current user")
        except:
            print("Could not check SPI device permissions")
    else:
        print("❌ SPI device /dev/spidev0.0 does NOT exist")

def check_gpio_interface():
    """Check if the GPIO interface is accessible"""
    print("\n=== GPIO INTERFACE CHECK ===")
    
    # Check if GPIO device exists
    if os.path.exists('/dev/gpiochip0'):
        print("✅ GPIO device /dev/gpiochip0 exists")
        try:
            permissions = oct(os.stat('/dev/gpiochip0').st_mode)[-3:]
            print(f"   Permissions: {permissions}")
            if int(permissions[2]) >= 4:  # Check if world-readable
                print("✅ GPIO device is readable by current user")
            else:
                print("❌ GPIO device is NOT readable by current user")
        except:
            print("Could not check GPIO device permissions")
    else:
        print("❌ GPIO device /dev/gpiochip0 does NOT exist")
    
    # Check if user is in gpio group
    try:
        groups = subprocess.check_output(["groups"]).decode()
        if "gpio" in groups.split():
            print("✅ Current user is in the gpio group")
        else:
            print("❌ Current user is NOT in the gpio group")
    except:
        print("Could not check if user is in gpio group")

def attempt_spidev_import():
    """Attempt to import spidev and diagnose issues"""
    print("\n=== SPIDEV MODULE IMPORT TEST ===")
    
    try:
        import spidev
        print(f"✅ Successfully imported spidev module (version: {spidev.__version__ if hasattr(spidev, '__version__') else 'unknown'})")
        
        # Test SPI device opening
        try:
            spi = spidev.SpiDev()
            spi.open(0, 0)
            print("✅ Successfully opened SPI device")
            print(f"   Max speed: {spi.max_speed_hz}")
            print(f"   Mode: {spi.mode}")
            spi.close()
        except Exception as e:
            print(f"❌ Failed to open SPI device: {e}")
    except ImportError as e:
        print(f"❌ Failed to import spidev module: {e}")
        print("\nPossible solutions:")
        print("1. Install spidev: sudo pip3 install spidev")
        print("2. Make sure SPI is enabled: sudo raspi-config nonint do_spi 0")
        print("3. Reboot: sudo reboot")
    except Exception as e:
        print(f"❌ Unexpected error with spidev: {e}")
        print(f"   {traceback.format_exc()}")

def test_eink_driver():
    """Test the E-Ink driver directly"""
    print("\n=== E-INK DRIVER TEST ===")
    
    try:
        from devices.eink.drivers.waveshare_3in7_pi5 import Driver
        print("✅ Successfully imported the E-Ink driver module")
        
        try:
            driver = Driver()
            print(f"✅ Successfully created driver instance")
            print(f"   Hardware mode: {'Enabled' if driver.USE_HARDWARE else 'Disabled (using mock)'}")
            if driver.USE_HARDWARE:
                print("✅ Hardware initialization successful")
            else:
                print("❌ Hardware initialization failed - using mock mode")
        except Exception as e:
            print(f"❌ Failed to create driver instance: {e}")
            print(f"   {traceback.format_exc()}")
    except ImportError as e:
        print(f"❌ Failed to import E-Ink driver module: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"   {traceback.format_exc()}")

def fix_permissions():
    """Attempt to fix common permission issues"""
    print("\n=== FIXING PERMISSIONS ===")
    print("This requires sudo access.")
    
    # Check if running as root
    if os.geteuid() != 0:
        print("This section requires root privileges.")
        print("Please run the script with sudo.")
        return
    
    # Fix SPI permissions
    if os.path.exists('/dev/spidev0.0'):
        try:
            os.chmod('/dev/spidev0.0', 0o666)
            print("✅ Set permissions for /dev/spidev0.0")
        except Exception as e:
            print(f"❌ Failed to set permissions for /dev/spidev0.0: {e}")
    
    if os.path.exists('/dev/spidev0.1'):
        try:
            os.chmod('/dev/spidev0.1', 0o666)
            print("✅ Set permissions for /dev/spidev0.1")
        except Exception as e:
            print(f"❌ Failed to set permissions for /dev/spidev0.1: {e}")
    
    # Fix GPIO permissions
    if os.path.exists('/dev/gpiochip0'):
        try:
            os.chmod('/dev/gpiochip0', 0o666)
            print("✅ Set permissions for /dev/gpiochip0")
        except Exception as e:
            print(f"❌ Failed to set permissions for /dev/gpiochip0: {e}")
    
    if os.path.exists('/dev/gpiomem'):
        try:
            os.chmod('/dev/gpiomem', 0o666)
            print("✅ Set permissions for /dev/gpiomem")
        except Exception as e:
            print(f"❌ Failed to set permissions for /dev/gpiomem: {e}")
            
    # Create udev rules for persistent permissions
    udev_rule = """
SUBSYSTEM=="spidev", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
"""
    try:
        with open('/etc/udev/rules.d/99-spi-gpio.rules', 'w') as f:
            f.write(udev_rule)
        print("✅ Created udev rules for persistent permissions")
        
        try:
            subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
            subprocess.run(["udevadm", "trigger"], check=True)
            print("✅ Reloaded udev rules")
        except Exception as e:
            print(f"❌ Failed to reload udev rules: {e}")
    except Exception as e:
        print(f"❌ Failed to create udev rules: {e}")

def print_fix_instructions():
    """Print instructions for fixing detected issues"""
    print("\n=== FIX INSTRUCTIONS ===")
    print("To fix the issues with the E-Ink display, run the following commands:")
    print("\n1. Install required packages:")
    print("   sudo apt-get update")
    print("   sudo apt-get install -y python3-pip python3-dev python3-setuptools python3-wheel python3-gpiod libgpiod-dev i2c-tools spi-tools")
    
    print("\n2. Install required Python modules:")
    print("   sudo pip3 install spidev numpy pillow gpiod")
    
    print("\n3. Enable SPI interface:")
    print("   sudo raspi-config nonint do_spi 0")
    
    print("\n4. Fix permissions:")
    print("   sudo chmod 666 /dev/spidev0.0 /dev/spidev0.1 /dev/gpiochip0")
    print("   sudo usermod -a -G gpio $USER")
    
    print("\n5. Create udev rules for persistent permissions:")
    print("""   sudo tee /etc/udev/rules.d/99-spi-gpio.rules > /dev/null << EOF
SUBSYSTEM=="spidev", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
EOF""")
    print("   sudo udevadm control --reload-rules && sudo udevadm trigger")
    
    print("\n6. Reboot to apply all changes:")
    print("   sudo reboot")
    
    print("\nAlternatively, run our automated fix script:")
    print("   sudo python/scripts/fix_eink_dependencies.sh")

def main():
    """Main function to run all diagnostic checks"""
    # Setup logging
    try:
        setup_logger(level=10)  # Debug level
    except:
        pass  # Use basic logging if setup_logger fails
    
    print("=== E-INK DISPLAY DIAGNOSTIC ===")
    print("This script will diagnose issues with the E-Ink display")
    
    check_system_info()
    modules_ok = check_required_modules()
    check_system_packages()
    check_spi_interface()
    check_gpio_interface()
    attempt_spidev_import()
    test_eink_driver()
    
    # Only attempt to fix permissions if running as root
    if os.geteuid() == 0:
        fix_permissions()
    else:
        print_fix_instructions()
    
    print("\n=== DIAGNOSTIC COMPLETE ===")
    print("Check the output above for issues and follow the fix instructions.")

if __name__ == "__main__":
    main() 