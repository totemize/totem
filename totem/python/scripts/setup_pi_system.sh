#!/bin/bash
# Comprehensive Raspberry Pi system setup script for Totem
# Sets up all necessary system dependencies and configurations

set -e  # Exit on error

echo "============================================"
echo "Totem: Raspberry Pi System Setup"
echo "============================================"

# Make backup of original script if it exists
if [ -f "$(dirname "$0")/setup_dependencies.sh" ]; then
    cp "$(dirname "$0")/setup_dependencies.sh" "$(dirname "$0")/setup_dependencies.sh.bak"
    echo "Backed up original setup_dependencies.sh"
fi

# Function to safely install packages
install_package() {
    local package=$1
    echo "Installing $package..."
    if ! sudo apt-get install -y "$package"; then
        echo "Warning: Failed to install $package, checking alternatives..."
        # Try alternative packages based on common substitutions
        case "$package" in
            "libtiff5")
                # Try libtiff6 or libtiff5-dev instead
                sudo apt-get install -y libtiff6 || sudo apt-get install -y libtiff5-dev || true
                ;;
            *)
                echo "No alternative found for $package"
                ;;
        esac
    fi
}

# 1. Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Enable required interfaces
echo "Enabling required interfaces (SPI, I2C)..."
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
    echo "Enabling SPI..."
    sudo raspi-config nonint do_spi 0
fi

if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "Enabling I2C..."
    sudo raspi-config nonint do_i2c 0
fi

# 3. Install essential system packages
echo "Installing essential system packages..."
ESSENTIAL_PACKAGES=(
    python3
    python3-pip
    python3-venv
    python3-dev
    build-essential
    git
    i2c-tools
    spi-tools
)

for package in "${ESSENTIAL_PACKAGES[@]}"; do
    if ! dpkg -l | grep -q "^ii  $package "; then
        install_package "$package"
    else
        echo "$package already installed."
    fi
done

# 4. Install E-Ink display dependencies
echo "Installing E-Ink display dependencies..."
EINK_PACKAGES=(
    libffi-dev
    libssl-dev
    libjpeg-dev
    libopenjp2-7
    libtiff6       # Changed from libtiff5 to libtiff6 for Debian Bookworm
    libatlas-base-dev
    libfreetype6-dev
    liblcms2-dev
    libwebp-dev
    zlib1g-dev
    libharfbuzz-dev
    libfribidi-dev
    libxcb1-dev
    fonts-dejavu-core
    python3-gpiod
)

for package in "${ESSENTIAL_PACKAGES[@]}"; do
    if ! dpkg -l | grep -q "^ii  $package "; then
        install_package "$package"
    else
        echo "$package already installed."
    fi
done

# 5. Configure GPIO access permissions
echo "Configuring GPIO access permissions..."
if ! getent group gpio > /dev/null; then
    sudo groupadd -f gpio
fi

if ! id -nG "$(whoami)" | grep -qw "gpio"; then
    sudo usermod -aG gpio "$(whoami)"
    echo "Added current user to gpio group. You may need to log out and back in for this to take effect."
fi

# Create a udev rule for persistent permissions
cat << EOF | sudo tee /etc/udev/rules.d/99-gpio-permissions.rules > /dev/null
SUBSYSTEM=="gpio*", PROGRAM="/bin/sh -c 'chown -R root:gpio /sys/class/gpio && chmod -R 770 /sys/class/gpio'"
SUBSYSTEM=="spidev", GROUP="gpio", MODE="0660"
KERNEL=="gpiomem", GROUP="gpio", MODE="0660"
KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

# 6. Install Poetry for Python dependency management
echo "Installing Poetry..."
if ! command -v poetry &> /dev/null; then
    curl -sSL https://install.python-poetry.org | python3 -
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
else
    echo "Poetry already installed."
fi

# Add PATH to current session
export PATH="$HOME/.local/bin:$PATH"

echo "============================================"
echo "System dependencies installed successfully!"
echo "Please restart your Raspberry Pi to apply all changes."
echo "============================================" 