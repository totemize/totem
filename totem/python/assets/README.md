# Assets Directory

This directory contains various assets used by the Python modules in this project.

## Contents

- `bitmap-sample.bmp`: A sample bitmap image used for testing the e-ink display. This is the default image used by the `display_image_file.py` script when no image path is provided.

## Usage

When adding new assets to this directory, please update this README file to document their purpose and usage.

For using the bitmap sample with the e-ink display:

```bash
# Display the default bitmap sample
sudo python3 python/examples/display_image_file.py

# Or specify it explicitly
sudo python3 python/examples/display_image_file.py python/assets/bitmap-sample.bmp
``` 