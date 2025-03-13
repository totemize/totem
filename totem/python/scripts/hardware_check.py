#!/usr/bin/env python3
"""
Hardware check script to identify potential conflicts between NVMe HAT and E-Ink display
"""

import os
import sys
import subprocess
import time

def run_command(cmd):
    """Run a shell command and return the output"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stdout:
            print("OUTPUT:")
            print(result.stdout)
        if result.stderr:
            print("ERRORS:")
            print(result.stderr)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print("OUTPUT:")
            print(e.stdout)
        if e.stderr:
            print("ERRORS:")
            print(e.stderr)
        return None

def check_pin_status():
    """Check the status of GPIO pins"""
    print("\n=== GPIO PIN STATUS ===")
    
    # List of pins used by E-Ink display
    eink_pins = [17, 25, 24, 8]  # Original pins
    eink_alt_pins = [27, 22, 23, 7]  # Alternative pins
    
    # Check if gpiochip0 exists
    if not os.path.exists('/dev/gpiochip0'):
        print("GPIO chip not found at /dev/gpiochip0")
        return
    
    # Check gpio utility if available
    run_command("gpio readall 2>/dev/null || echo 'gpio utility not available'")
    
    # Check gpio exports
    run_command("ls -la /sys/class/gpio/")
    
    # Try to manually check each pin
    for pin in eink_pins + eink_alt_pins:
        print(f"\nChecking pin {pin}:")
        # Try to export the pin
        run_command(f"echo {pin} > /sys/class/gpio/export 2>/dev/null || echo 'Pin {pin} might be in use'")
        # Check if the pin directory exists
        run_command(f"ls -la /sys/class/gpio/gpio{pin} 2>/dev/null || echo 'Pin {pin} not exported'")
        # Unexport the pin
        run_command(f"echo {pin} > /sys/class/gpio/unexport 2>/dev/null || echo 'Could not unexport pin {pin}'")

def check_spi_devices():
    """Check SPI devices"""
    print("\n=== SPI DEVICES ===")
    run_command("ls -la /dev/spidev*")
    run_command("cat /boot/config.txt | grep -i spi")
    run_command("lsmod | grep spi")

def check_nvme_status():
    """Check NVMe status"""
    print("\n=== NVME STATUS ===")
    run_command("lsblk")
    run_command("dmesg | grep -i nvme")
    run_command("lsmod | grep nvme")
    run_command("ls -la /dev/nvme*")
    
    # Try to find information about NVMe hat
    print("\nNVMe HAT information:")
    run_command("cat /proc/device-tree/hat/product 2>/dev/null || echo 'No HAT product info found'")
    run_command("cat /proc/device-tree/hat/vendor 2>/dev/null || echo 'No HAT vendor info found'")

def check_power_status():
    """Check power status"""
    print("\n=== POWER STATUS ===")
    run_command("vcgencmd measure_volts")
    run_command("vcgencmd measure_temp")
    run_command("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 'CPU frequency info not available'")

def check_running_processes():
    """Check for any processes that might be using the hardware"""
    print("\n=== RUNNING PROCESSES ===")
    run_command("ps aux | grep -i python | grep -v grep")
    run_command("ps aux | grep -i spi | grep -v grep")
    run_command("ps aux | grep -i gpio | grep -v grep")
    
    # Kill any existing Python processes that might be holding resources
    print("\nKilling any Python processes that might be holding hardware resources:")
    run_command("sudo pkill -9 -f python || echo 'No Python processes to kill'")

def check_hardware_libs():
    """Check if the hardware libraries are available and their versions"""
    print("\n=== HARDWARE LIBRARIES ===")
    
    # Check RPi.GPIO
    print("\nRPi.GPIO:")
    try:
        import RPi.GPIO as GPIO
        print(f"RPi.GPIO version: {GPIO.VERSION}")
        print("RPi.GPIO is available")
    except ImportError:
        print("RPi.GPIO is not available")
    
    # Check spidev
    print("\nspidev:")
    try:
        import spidev
        print("spidev is available")
    except ImportError:
        print("spidev is not available")
    
    # Check gpiod
    print("\ngpiod:")
    try:
        import gpiod
        print("gpiod is available")
        
        # Check if v2 API is available
        try:
            from gpiod.line_settings import LineSettings
            print("gpiod v2 API is available")
        except ImportError:
            print("gpiod v1 API is available")
    except ImportError:
        print("gpiod is not available")

def main():
    """Main function"""
    print("=== HARDWARE CHECK SCRIPT ===")
    print("Checking for conflicts between NVMe HAT and E-Ink display\n")
    
    # Check running processes
    check_running_processes()
    
    # Check hardware libraries
    check_hardware_libs()
    
    # Check power status
    check_power_status()
    
    # Check NVMe status
    check_nvme_status()
    
    # Check SPI devices
    check_spi_devices()
    
    # Check GPIO pin status
    check_pin_status()
    
    print("\n=== HARDWARE CHECK COMPLETE ===")
    print("Check the output above for any conflicts between NVMe HAT and E-Ink display")

if __name__ == "__main__":
    main() 