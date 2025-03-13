# Waveshare E-Ink Manufacturer Examples

This directory contains example scripts from the Waveshare e-Paper manufacturer, adapted to work with our project structure.

## Prerequisites

The examples require the Waveshare e-Paper driver to be installed. We've provided a helper script to install it:

```bash
sudo python3 ../install_waveshare_driver.py
```

## Running the Examples

### 3.7 inch E-Ink Display

To run the 3.7 inch display example:

```bash
# Option 1: Run directly
sudo python3 epd_3in7_test.py

# Option 2: Use the helper script
sudo ../run_manufacturer_test.sh
```

The example will:
1. Initialize the display
2. Clear the screen
3. Draw text and shapes in different gray levels
4. Show a clock with partial updates
5. Put the display to sleep

## Troubleshooting

If you encounter the error `ModuleNotFoundError: No module named 'waveshare_epd'`, run the installation script:

```bash
sudo python3 ../install_waveshare_driver.py
```

## Hardware Connections

The examples assume the following GPIO connections:

### 3.7 inch E-Ink Display

| E-Ink Display | Raspberry Pi |
|---------------|--------------|
| VCC           | 3.3V         |
| GND           | GND          |
| DIN           | MOSI         |
| CLK           | SCLK         |
| CS            | CE0          |
| DC            | GPIO 25      |
| RST           | GPIO 17      |
| BUSY          | GPIO 24      |

You can customize these pins by setting environment variables before running the examples:

```bash
export EINK_RST_PIN=17
export EINK_DC_PIN=25
export EINK_CS_PIN=8
export EINK_BUSY_PIN=24
```

For software SPI (useful for Pi 5 or when avoiding hardware SPI conflicts):

```bash
export USE_SW_SPI=1
export EINK_MOSI_PIN=10
export EINK_SCK_PIN=11
``` 