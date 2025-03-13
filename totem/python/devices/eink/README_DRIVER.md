# Waveshare E-Paper Driver Integration

## Overview

This project uses Waveshare e-Paper displays. To avoid hardcoded dependencies and make the project more maintainable, we've integrated the necessary Waveshare driver files directly into our project as a Poetry package.

## How It Works

1. The Waveshare driver files (`epd3in7.py` and `epdconfig.py`) are included in the project under `python/devices/eink/waveshare_epd/`.

2. The e-ink device's `pyproject.toml` includes this package, making it available as a Poetry dependency.

3. Our driver (`waveshare_3in7.py`) tries to import the Waveshare driver from two locations:
   - First, from the system-installed module (if available)
   - If not found, it falls back to our local package

## Adding Support for Other Displays

To add support for another Waveshare display model:

1. Copy the required driver file (e.g., `epd2in13.py`) from the Waveshare repository to `python/devices/eink/waveshare_epd/`.

2. Create a new driver class in `python/devices/eink/drivers/` that follows the same pattern as `waveshare_3in7.py`.

## Updating the Driver

If you need to update the Waveshare driver files:

1. Download the latest files from the [Waveshare repository](https://github.com/waveshare/e-Paper).

2. Replace the files in `python/devices/eink/waveshare_epd/` with the updated versions.

3. Test to ensure compatibility. 