#!/bin/bash
# E-Ink Display Test Runner
# This script allows testing of different E-Ink displays

# Set the base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/../.." &> /dev/null && pwd)"
TESTS_DIR="${BASE_DIR}/python/tests"

# Function to run a test script
run_test() {
  local script_path="$1"
  echo "Running test script: $script_path"
  
  # Get the directory of the script for Python to find modules
  cd "$(dirname "$script_path")" || exit 1
  python3 "$(basename "$script_path")"
  return $?
}

# Function to check for the spidev module
check_spidev() {
  python3 -c "import spidev" &> /dev/null
  if [ $? -ne 0 ]; then
    echo "ERROR: spidev module is not available."
    echo "Would you like to run the dependency fix script now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
      sudo "${SCRIPT_DIR}/fix_eink_dependencies.sh"
      echo "Please reboot your system and run this script again."
      exit 1
    else
      echo "Cannot continue without spidev. Exiting."
      exit 1
    fi
  fi
}

# Main menu
echo "=== E-Ink Display Test ==="
echo "Please select the display to test:"
echo "1) 2.13-inch E-Paper HAT (250×122)"
echo "2) 3.7-inch E-Paper HAT (480×280)"
echo "3) Run system diagnostics"
echo "4) Install/fix dependencies"
echo "q) Quit"

read -r choice
case $choice in
  1)
    echo "Testing 2.13-inch E-Paper HAT..."
    check_spidev
    if [ -f "${TESTS_DIR}/test_2in13_eink.py" ]; then
      run_test "${TESTS_DIR}/test_2in13_eink.py"
    else
      echo "2.13-inch test script not found at: ${TESTS_DIR}/test_2in13_eink.py"
      echo "Using the script at: ${SCRIPT_DIR}/test_2in13_eink.py instead"
      run_test "${SCRIPT_DIR}/test_2in13_eink.py"
    fi
    ;;
  2)
    echo "Testing 3.7-inch E-Paper HAT..."
    check_spidev
    if [ -f "${TESTS_DIR}/test_pi5_eink.py" ]; then
      run_test "${TESTS_DIR}/test_pi5_eink.py"
    else
      echo "Error: 3.7-inch test script not found at: ${TESTS_DIR}/test_pi5_eink.py"
      exit 1
    fi
    ;;
  3)
    echo "Running E-Ink display diagnostics..."
    # Try to run the diagnostic script
    diagnostic_script="${SCRIPT_DIR}/eink_diagnostics.py"
    if [ -f "$diagnostic_script" ]; then
      python3 "$diagnostic_script"
    else
      echo "Diagnostic script not found at: $diagnostic_script"
      exit 1
    fi
    ;;
  4)
    echo "Installing/fixing E-Ink dependencies..."
    sudo "${SCRIPT_DIR}/fix_eink_dependencies.sh"
    ;;
  q|Q)
    echo "Exiting."
    exit 0
    ;;
  *)
    echo "Invalid option. Exiting."
    exit 1
    ;;
esac

exit 0 