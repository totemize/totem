#!/usr/bin/env python3
"""Render a controller-native framebuffer through a selected display driver."""

import argparse
from pathlib import Path

from totem.managers.display_manager import DisplayManager


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frame", type=Path, help="raw controller framebuffer file")
    parser.add_argument("--driver", required=True, help="registered display driver")
    args = parser.parse_args()

    if not args.frame.is_file():
        parser.error("frame must be an existing file")

    display = DisplayManager(driver_name=args.driver, allow_mock=False)
    try:
        display.display_bytes(args.frame.read_bytes())
        display.sleep()
    finally:
        display.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
