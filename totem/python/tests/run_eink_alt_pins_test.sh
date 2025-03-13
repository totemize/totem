#!/bin/bash
# Run the EInk test with alternative pins and software SPI

# Set the directory to the project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
TOTEM_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$TOTEM_DIR"

# Set environment variables for alternative pins
export USE_ALT_EINK_PINS=1
export EINK_RST_PIN=17  # Default is 17, which is free
export EINK_DC_PIN=25   # Default is 25, which is free
export EINK_CS_PIN=9    # Use pin 9 instead of 8 (which is busy)
export EINK_BUSY_PIN=24 # Default is 24, which is free
export PYTHONPATH="${TOTEM_DIR}"

# Enable software SPI mode
export USE_SW_SPI=1
export EINK_MOSI_PIN=10 # Default is 10, which is free
export EINK_SCK_PIN=11  # Default is 11, which is free

echo "Running EInk test with alternative pins and software SPI"
echo "PYTHONPATH: ${PYTHONPATH}"
echo "Using pins: RST=${EINK_RST_PIN}, DC=${EINK_DC_PIN}, CS=${EINK_CS_PIN}, BUSY=${EINK_BUSY_PIN}"
echo "Software SPI pins: MOSI=${EINK_MOSI_PIN}, SCK=${EINK_SCK_PIN}"
echo "Software SPI: ${USE_SW_SPI}"

# Run the test script
python3 python/tests/test_eink_alt_pins.py

exit $? 