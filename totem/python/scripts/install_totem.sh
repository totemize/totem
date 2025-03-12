#!/bin/bash
# Main installation script for Totem on Raspberry Pi 5
# This script orchestrates the complete setup by calling component scripts in the correct order

# Don't exit immediately on error, we'll handle errors ourselves
set +e

# Define text colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default configuration
WIFI_SSID="TotemAP"
WIFI_PASSWORD="totempassword"
WIFI_CHANNEL=7
WIFI_COUNTRY="US"
SKIP_CONFIRM=false
SCRIPTS_DIR="$(dirname "$0")"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}     Totem: Complete Raspberry Pi 5 Setup   ${NC}"
echo -e "${GREEN}============================================${NC}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ssid)
            WIFI_SSID="$2"
            shift 2
            ;;
        --password)
            WIFI_PASSWORD="$2"
            shift 2
            ;;
        --channel)
            WIFI_CHANNEL="$2"
            shift 2
            ;;
        --country)
            WIFI_COUNTRY="$2"
            shift 2
            ;;
        --yes)
            SKIP_CONFIRM=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown parameter: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if running on Raspberry Pi
if [ ! -f /proc/cpuinfo ]; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi.${NC}"
    if [ "$SKIP_CONFIRM" = false ]; then
        read -p "Do you want to continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}Installation aborted.${NC}"
            exit 1
        fi
    fi
else
    PI_MODEL=$(grep -oP 'Model\s*:\s*\K.*' /proc/cpuinfo 2>/dev/null | head -n 1)
    if [[ -n "$PI_MODEL" && ! $PI_MODEL =~ "Raspberry Pi 5" ]]; then
        echo -e "${YELLOW}Warning: This appears to be $PI_MODEL, not a Raspberry Pi 5.${NC}"
        echo -e "${YELLOW}The scripts are optimized for Raspberry Pi 5 with Raspberry Pi OS.${NC}"
        
        if [ "$SKIP_CONFIRM" = false ]; then
            read -p "Do you want to continue anyway? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${RED}Installation aborted.${NC}"
                exit 1
            fi
        fi
    fi
fi

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YELLOW}This script requires root privileges.${NC}"
    echo -e "${YELLOW}Switching to sudo...${NC}"
    
    # Re-run the script with sudo, preserving arguments
    exec sudo "$0" "$@"
    exit $?
fi

# Make sure all scripts are executable
echo "Ensuring all scripts are executable..."
chmod +x "$SCRIPTS_DIR/setup_pi_system.sh"
chmod +x "$SCRIPTS_DIR/setup_wifi_hotspot.sh"
chmod +x "$SCRIPTS_DIR/setup_network_routing.sh"

# Display installation plan
echo -e "${GREEN}Installation Plan:${NC}"
echo "1. System dependencies and GPIO configuration"
echo "2. Wi-Fi hotspot setup (SSID: $WIFI_SSID)"
echo "3. Network routing configuration"

# Confirmation
if [ "$SKIP_CONFIRM" = false ]; then
    echo
    echo -e "${YELLOW}Warning: This script will make significant changes to your system.${NC}"
    echo -e "${YELLOW}It's recommended to make a backup before proceeding.${NC}"
    echo
    read -p "Do you want to proceed with the installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Installation aborted.${NC}"
        exit 1
    fi
fi

# Step 1: System setup
echo -e "\n${GREEN}Step 1/3: Setting up system dependencies and GPIO configuration...${NC}"
"$SCRIPTS_DIR/setup_pi_system.sh"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ System setup completed successfully${NC}"
else
    echo -e "${RED}✗ System setup failed${NC}"
    echo -e "${YELLOW}Would you like to continue with the remaining steps? (y/N)${NC}"
    if [ "$SKIP_CONFIRM" = false ]; then
        read -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}Installation aborted.${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}Continuing with installation despite errors...${NC}"
    fi
fi

# Step 2: Wi-Fi hotspot setup
echo -e "\n${GREEN}Step 2/3: Setting up Wi-Fi hotspot...${NC}"
"$SCRIPTS_DIR/setup_wifi_hotspot.sh" --ssid "$WIFI_SSID" --password "$WIFI_PASSWORD" \
    --channel "$WIFI_CHANNEL" --country "$WIFI_COUNTRY"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Wi-Fi hotspot setup completed successfully${NC}"
else
    echo -e "${RED}✗ Wi-Fi hotspot setup failed${NC}"
    echo -e "${YELLOW}Would you like to continue with the remaining steps? (y/N)${NC}"
    if [ "$SKIP_CONFIRM" = false ]; then
        read -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}Installation aborted.${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}Continuing with installation despite errors...${NC}"
    fi
fi

# Step 3: Network routing setup
echo -e "\n${GREEN}Step 3/3: Setting up network routing...${NC}"
"$SCRIPTS_DIR/setup_network_routing.sh"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Network routing setup completed successfully${NC}"
else
    echo -e "${RED}✗ Network routing setup failed${NC}"
    # This is the last step, so we don't need to ask about continuing
fi

# Installation complete
echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}     Totem Installation Complete!      ${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "Wi-Fi Hotspot Details:"
echo -e "  SSID: ${YELLOW}$WIFI_SSID${NC}"
echo -e "  Password: ${YELLOW}$WIFI_PASSWORD${NC}"
echo -e "\nTo apply all changes, please restart your Raspberry Pi:"
echo -e "${YELLOW}sudo reboot${NC}"
echo -e "${GREEN}============================================${NC}"

# Offer to reboot
if [ "$SKIP_CONFIRM" = false ]; then
    read -p "Would you like to reboot now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Rebooting now..."
        reboot
    fi
fi

exit 0 