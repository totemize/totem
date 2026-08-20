#!/usr/bin/env python3
"""Render an image file through an explicitly selected display driver."""

import argparse
from pathlib import Path

from totem.managers.display_manager import DisplayManager


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="PNG, JPEG, or other PIL image")
    parser.add_argument("--driver", required=True, help="registered display driver")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error("image must be an existing file")

    display = DisplayManager(driver_name=args.driver, allow_mock=False)
    try:
        display.display_image_from_file(str(args.image))
        display.sleep()
    finally:
        display.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
