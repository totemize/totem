#!/usr/bin/env python3
"""Render text through an explicitly selected Totem display driver."""

import argparse
from pathlib import Path

from totem.managers.display_manager import DisplayManager


DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", required=True, help="registered display driver")
    parser.add_argument("--text", required=True, help="text to render")
    parser.add_argument("--font-size", type=int, default=24)
    parser.add_argument("--x", type=int, default=14)
    parser.add_argument("--y", type=int, default=26)
    parser.add_argument("--font", default=DEFAULT_FONT)
    args = parser.parse_args()

    font = args.font if Path(args.font).is_file() else None
    display = DisplayManager(driver_name=args.driver, allow_mock=False)
    try:
        display.display_text(
            args.text,
            font_size=args.font_size,
            x=args.x,
            y=args.y,
            font_name=font,
        )
        display.sleep()
    finally:
        display.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
