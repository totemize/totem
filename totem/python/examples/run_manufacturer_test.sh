#!/bin/bash
# Run the Waveshare manufacturer's example script
# This script:
# 1. Installs the Waveshare driver if needed
# 2. Runs the manufacturer's example script

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Waveshare E-Ink Display Test ===${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root (sudo) to access GPIO pins${NC}"
  exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${YELLOW}Installing Waveshare driver if needed...${NC}"
python3 "$SCRIPT_DIR/install_waveshare_driver.py"
if [ $? -ne 0 ]; then
  echo -e "${RED}Driver installation failed, but we'll try to run the example anyway${NC}"
fi

# Check if the manufacturer directory exists
if [ ! -d "$SCRIPT_DIR/manufacturer" ]; then
  echo -e "${RED}Manufacturer directory not found. Creating it...${NC}"
  mkdir -p "$SCRIPT_DIR/manufacturer"
fi

# Check if the example script exists
if [ ! -f "$SCRIPT_DIR/manufacturer/epd_3in7_test.py" ]; then
  echo -e "${RED}Example script not found. Please make sure it exists at:${NC}"
  echo -e "${RED}$SCRIPT_DIR/manufacturer/epd_3in7_test.py${NC}"
  exit 1
fi

echo -e "${YELLOW}Running manufacturer's example script...${NC}"
cd "$SCRIPT_DIR/manufacturer"
python3 epd_3in7_test.py
if [ $? -ne 0 ]; then
  echo -e "${RED}Example script failed. Please check the error messages above.${NC}"
  exit 1
fi

echo -e "${GREEN}Test complete!${NC}" 