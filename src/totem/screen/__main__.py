"""Command-line entry point for the e-ink screen state service."""

import argparse
import asyncio
import logging
import os
import signal

from totem.logging import setup_logger
from totem.screen.controller import ScreenController
from totem.screen.display import DeviceManagerDisplay
from totem.screen.readiness import (
    LiveReadinessMonitor,
    SyntheticReadinessMonitor,
)
from totem.screen.render import FrameRenderer
from totem.screen.systemd import SystemdNotifier


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Totem screen state service")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "replay-boot"),
    )
    parser.add_argument(
        "--device-api-url",
        default=os.environ.get("TOTEM_DEVICE_API_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument(
        "--width",
        type=int,
        default=int(os.environ.get("TOTEM_SCREEN_WIDTH", "250")),
    )
    parser.add_argument(
        "--height",
        type=int,
        default=int(os.environ.get("TOTEM_SCREEN_HEIGHT", "122")),
    )
    parser.add_argument(
        "--rotation",
        type=int,
        choices=(0, 180),
        default=int(os.environ.get("TOTEM_SCREEN_ROTATION", "0")),
    )
    parser.add_argument(
        "--log-level",
        choices=("debug", "info", "warning", "error"),
        default="info",
    )
    return parser


async def _run(args) -> None:
    display = DeviceManagerDisplay(args.device_api_url)
    renderer = FrameRenderer(
        width=args.width,
        height=args.height,
        rotation=args.rotation,
    )
    controller = ScreenController(display, renderer)
    if args.command == "replay-boot":
        monitor = SyntheticReadinessMonitor()
        notifier = SystemdNotifier(address="")
    else:
        monitor = LiveReadinessMonitor(display)
        notifier = SystemdNotifier()

    await controller.boot(
        monitor,
        notifier,
        poll_interval=args.poll_interval,
        settle_seconds=args.settle_seconds,
    )

    if args.command == "run":
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stop.set)
        await stop.wait()


def main() -> None:
    args = _parser().parse_args()
    setup_logger(level=getattr(logging, args.log_level.upper()))
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
