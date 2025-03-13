#!/bin/bash
# Test script for the EInk service and display system
# This script runs through various tests to verify the system is working properly

# Default display type
DISPLAY_TYPE=${EINK_DISPLAY_TYPE:-waveshare_3in7}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status messages
function echo_status() {
  echo -e "${BLUE}[STATUS]${NC} $1"
}

function echo_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function echo_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

function echo_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if a command succeeded
function check_result() {
  if [ $? -eq 0 ]; then
    echo_success "$1"
    return 0
  else
    echo_error "$2"
    return 1
  fi
}

# Go to the project directory
cd "$(dirname "$(dirname "$(dirname "$0")")")" || exit 1
echo_status "Working directory: $(pwd)"

# Start with cleanup
echo_status "Cleaning up any existing resources..."
python3 -m python.scripts.stop_eink_service --force
check_result "Stopped existing EInk service" "Failed to stop EInk service, continuing anyway"

# Check for processes using GPIO
echo_status "Checking for processes using GPIO..."
PROCESSES=$(lsof /dev/gpiochip0 2>/dev/null)
if [ -n "$PROCESSES" ]; then
  echo_warning "Found processes using GPIO:"
  echo "$PROCESSES"
  
  # Ask for confirmation before killing
  read -p "Do you want to kill these processes? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo_status "Attempting to free GPIO resources..."
    python3 -m python.scripts.start_eink_service cleanup
    check_result "Cleaned up GPIO resources" "Failed to clean up GPIO resources"
  fi
else
  echo_success "No processes found using GPIO"
fi

# Run system test in direct mode
echo_status "Testing direct mode..."
EINK_DISPLAY_TYPE=$DISPLAY_TYPE python3 -m python.tests.test_eink_service --mode direct
check_result "Direct mode test passed" "Direct mode test failed"

# Start the EInk service
echo_status "Starting EInk service..."
EINK_DISPLAY_TYPE=$DISPLAY_TYPE python3 -m python.scripts.start_eink_service start --force
check_result "Started EInk service" "Failed to start EInk service"

# Check service status
echo_status "Checking service status..."
python3 -m python.scripts.start_eink_service status
check_result "Service status check passed" "Service status check failed"

# Run quick service test
echo_status "Testing service mode..."
EINK_DISPLAY_TYPE=$DISPLAY_TYPE USE_EINK_SERVICE=1 python3 -c "
from python.managers.display_manager import DisplayManager
print('Creating DisplayManager...')
dm = DisplayManager()
print('Clearing screen...')
dm.clear_screen()
print('Displaying text...')
dm.display_text('Service\\nTest', font_size=36)
print('Done!')
"
check_result "Service mode test passed" "Service mode test failed"

# Show service log
echo_status "Service log:"
tail -n 20 /tmp/eink_service.log

# Ask if user wants to stop the service
read -p "Do you want to stop the EInk service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo_status "Stopping EInk service..."
  python3 -m python.scripts.stop_eink_service --force
  check_result "Stopped EInk service" "Failed to stop EInk service"
else
  echo_status "Leaving EInk service running"
fi

echo_success "All tests completed" 