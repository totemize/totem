#!/bin/bash
# E-Ink Dependencies Fix Script
# This script fixes issues with E-Ink display dependencies, particularly the spidev module
# Run with sudo: sudo ./fix_eink_dependencies.sh

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "=== E-Ink Display Dependencies Fix ==="
echo "This script will install required packages and configure your system for the Waveshare E-Ink display."

# Define required system packages
SYSTEM_PACKAGES=(
  "python3-pip"
  "python3-dev"
  "python3-setuptools"
  "python3-wheel"
  "python3-gpiod"
  "libgpiod-dev"
  "i2c-tools"
  "spi-tools"
)

# Define required Python packages (via apt)
PYTHON_APT_PACKAGES=(
  "python3-spidev"
  "python3-numpy"
  "python3-pil"
)

# Install system packages
echo -e "\n=== Installing system packages ==="
apt-get update
for package in "${SYSTEM_PACKAGES[@]}"; do
  if ! dpkg -l | grep -q "^ii  $package"; then
    echo "Installing $package..."
    apt-get install -y "$package"
  else
    echo "$package is already installed."
  fi
done

# Install Python packages using apt
echo -e "\n=== Installing Python packages using apt ==="
for package in "${PYTHON_APT_PACKAGES[@]}"; do
  if ! dpkg -l | grep -q "^ii  $package"; then
    echo "Installing $package..."
    apt-get install -y "$package"
  else
    echo "$package is already installed."
  fi
done

# Enable SPI interface if not already enabled
echo -e "\n=== Configuring SPI interface ==="
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
  echo "Enabling SPI interface..."
  if grep -q "^#dtparam=spi=on" /boot/config.txt; then
    # Uncomment existing line
    sed -i "s/^#dtparam=spi=on/dtparam=spi=on/" /boot/config.txt
  else
    # Add new line
    echo "dtparam=spi=on" >> /boot/config.txt
  fi
  echo "SPI interface enabled in /boot/config.txt"
  SPI_ENABLED=true
else
  echo "SPI interface already enabled."
  SPI_ENABLED=false
fi

# Set permissions for SPI and GPIO devices
echo -e "\n=== Setting device permissions ==="
if [ -e "/dev/spidev0.0" ]; then
  echo "Setting permissions for SPI devices..."
  chmod 666 /dev/spidev0.0
  chmod 666 /dev/spidev0.1
fi

if [ -e "/dev/gpiomem" ]; then
  echo "Setting permissions for GPIO devices..."
  chmod 666 /dev/gpiomem
fi

if [ -e "/dev/gpiochip0" ]; then
  echo "Setting permissions for GPIO chip devices..."
  chmod 666 /dev/gpiochip0
fi

# Create udev rule for persistent permissions if it doesn't exist
UDEV_RULE_FILE="/etc/udev/rules.d/99-spi-gpio.rules"
if [ ! -f "$UDEV_RULE_FILE" ]; then
  echo "Creating udev rules for persistent permissions..."
  cat > "$UDEV_RULE_FILE" << EOF
SUBSYSTEM=="spidev", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
EOF
  udevadm control --reload-rules && udevadm trigger
  echo "Udev rules created and applied."
fi

# Add current user to gpio group if not already a member
CURRENT_USER=$(logname || echo $SUDO_USER)
if [ -n "$CURRENT_USER" ] && ! groups "$CURRENT_USER" | grep -q "\bgpio\b"; then
  echo "Adding user $CURRENT_USER to gpio group..."
  usermod -a -G gpio "$CURRENT_USER"
  USER_ADDED=true
else
  echo "User is already a member of the gpio group or could not determine user."
  USER_ADDED=false
fi

# Summary
echo -e "\n=== E-Ink Dependencies Fix Complete ==="
echo "System packages installed: ${SYSTEM_PACKAGES[*]}"
echo "Python packages installed: ${PYTHON_APT_PACKAGES[*]}"
if [ "$SPI_ENABLED" = true ]; then
  echo "SPI interface has been enabled. A reboot is required."
fi
if [ "$USER_ADDED" = true ]; then
  echo "User $CURRENT_USER has been added to the gpio group. A logout/login is required."
fi

echo -e "\nIf you encounter any issues, please check the following:"
echo "- Run 'ls -l /dev/spidev*' to verify SPI device permissions"
echo "- Run 'lsmod | grep spi' to verify SPI modules are loaded"
echo "- Run 'gpio readall' to check GPIO status (if gpio utility is installed)"

# Recommend reboot if needed
if [ "$SPI_ENABLED" = true ] || [ "$USER_ADDED" = true ]; then
  echo -e "\nIMPORTANT: Please reboot your system to apply all changes:"
  echo "  sudo reboot"
fi

echo -e "\nTo test the E-Ink display after reboot, run:"
echo "  cd $(dirname "$0") && ./run_eink_test.sh"

exit 0 