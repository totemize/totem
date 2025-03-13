#!/bin/bash
# Run the EInk test with alternative pins and software SPI

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Set environment variables for alternative pins
export USE_ALT_EINK_PINS=1
export EINK_CS_PIN=7
export PYTHONPATH="${TOTEM_DIR}"

# Enable software SPI mode
export USE_SW_SPI=1
export EINK_MOSI_PIN=10
export EINK_SCK_PIN=11

echo "Running EInk test with alternative pins and software SPI"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Using pins: CS_PIN=${EINK_CS_PIN}, MOSI_PIN=${EINK_MOSI_PIN}, SCK_PIN=${EINK_SCK_PIN}"
echo "Software SPI: ${USE_SW_SPI}"

# Run the test script
python3 python/tests/test_eink_alt_pins.py

exit $? 