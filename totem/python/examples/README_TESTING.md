# E-Ink Display Testing Tools

We've created several tools to help test the e-ink display:

1. **Manufacturer's Example Script**: `python/examples/manufacturer/epd_3in7_test.py`
   - This is a modified version of the manufacturer's example script that works with our project structure.
   - Run with: `sudo ./run_manufacturer_test.sh`

2. **Direct Test Script**: `python/examples/run_direct_test.py`
   - This script uses our Driver class to test the e-ink display.
   - Run with: `sudo ./run_direct_test.py`

3. **Driver Installation Script**: `python/examples/install_waveshare_driver.py`
   - This script installs the Waveshare e-Paper driver on the Raspberry Pi.
   - Run with: `sudo python3 install_waveshare_driver.py`

4. **Image File Display Script**: `python/examples/display_image_file.py`
   - This script demonstrates how to display an image file on the e-ink display.
   - Run with: `sudo ./display_image_file.py /path/to/image.png`
   - Supports various image formats (PNG, JPG, BMP, etc.)
   - Automatically converts to grayscale and resizes to fit the display
   - Options:
     - `--no-resize`: Keep the original image size
     - `--mock`: Run in mock mode (no hardware required)

These tools should help with testing and debugging the e-ink display.
