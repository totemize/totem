# EInk Display Utilities

This directory contains utilities for testing and using the EInk display.

## `eink_message.py`

A flexible utility for displaying messages on the EInk display with various configuration options.

### Features

- Works in both normal mode and NVME-compatible mode
- Supports mock mode for testing without hardware
- Configurable font size and busy timeout
- Proper handling of multiline messages
- Detailed diagnostic output

### Usage Examples

```bash
# Display a simple message
python3 eink_message.py "Hello World"

# Display a message with NVME compatibility mode (uses software SPI)
python3 eink_message.py --nvme "This works with\nNVME hat installed"

# Test in mock mode (no hardware required)
python3 eink_message.py --mock "Testing in\nmock mode"

# Adjust timeout for busy checks (useful for slow displays)
python3 eink_message.py --timeout 20 "Using longer timeout"

# Display with custom font size
python3 eink_message.py --font-size 24 "Smaller text size"

# Combine options
python3 eink_message.py --nvme --font-size 48 --timeout 15 "Large text\nwith NVME mode"
```

### Environment Variables

The script supports all the environment variables used by the EInk driver:

- `NVME_COMPATIBLE=1`: Use GPIO pins that don't conflict with the NVME hat
- `EINK_MOCK_MODE=1`: Run in mock mode without hardware
- `EINK_BUSY_TIMEOUT=10`: Timeout in seconds for busy pin checks
- `EINK_RST_PIN`, `EINK_DC_PIN`, `EINK_CS_PIN`, `EINK_BUSY_PIN`: Custom pin assignments
- `USE_SW_SPI=1`: Force using software SPI
- `EINK_MOSI_PIN`, `EINK_SCK_PIN`: Software SPI pin assignments

## `run_eink_nvme_compatible.sh`

A shell script for testing the EInk display in NVME-compatible mode.

### Usage

```bash
./run_eink_nvme_compatible.sh "Your message here"
```

The script checks GPIO pin availability before attempting to use the display, and uses NVME-compatible pin settings 