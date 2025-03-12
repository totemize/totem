#!/bin/bash
# Setup NVMe Auto-Mount at Boot
# This script installs the necessary files to auto-mount NVMe at boot time

set -e  # Exit on error

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}     Totem: NVMe Auto-Mount Setup          ${NC}"
echo -e "${GREEN}============================================${NC}"

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}This script must be run as root${NC}"
    echo -e "Please run with: ${YELLOW}sudo $0${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make sure the boot script is executable
echo "Setting executable permissions on mount script..."
chmod +x "${SCRIPT_DIR}/mount_nvme_boot.sh"

# Copy systemd service file
echo "Installing systemd service..."
cp "${SCRIPT_DIR}/nvme-mount.service" /etc/systemd/system/

# Reload systemd daemon and enable service
echo "Enabling NVMe mount service..."
systemctl daemon-reload
systemctl enable nvme-mount.service

# Run the interactive setup script to configure the NVMe drive
echo "Running the interactive NVMe setup script..."
"${SCRIPT_DIR}/setup_nvme_mount.sh"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}     NVMe Auto-Mount Setup Complete!       ${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "The NVMe drive will now be automatically mounted at boot time."
echo -e "You can check the mount status after reboot with: ${YELLOW}df -h /mnt/nvme${NC}"
echo -e "Mount logs are stored in: ${YELLOW}/var/log/nvme-mount.log${NC}"
echo -e "${GREEN}============================================${NC}"

# Ask to reboot now
echo -e "${YELLOW}Would you like to reboot now to apply changes? (y/N)${NC}"
read -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rebooting system..."
    reboot
fi 