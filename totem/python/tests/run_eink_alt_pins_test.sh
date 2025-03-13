#!/bin/bash
# Run the EInk test with alternative pins

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Set environment variables for alternative pins
export USE_ALT_EINK_PINS=1
export EINK_CS_PIN=7
export PYTHONPATH="${TOTEM_DIR}"

echo "Running EInk test with alternative pins"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Using pins: CS_PIN=${EINK_CS_PIN}"

# Run the test script
python3 python/tests/test_eink_alt_pins.py

exit $? 