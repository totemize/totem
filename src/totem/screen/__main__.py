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
from totem.screen.runtime import (
    RuntimeController,
    RuntimePolicy,
    RuntimeSource,
    SnapshotUnavailable,
    TotemSnapshotClient,
    TotemdBus,
    TotemdEventStream,
    synthetic_snapshot,
)
from totem.screen.systemd import SystemdNotifier


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Totem screen state service")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=(
            "run",
            "replay-boot",
            "replay-states",
            "replay-all-states",
            "proof-captions",
        ),
    )
    parser.add_argument(
        "--device-api-url",
        default=os.environ.get("TOTEM_DEVICE_API_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument(
        "--totemd-bus-url",
        default=os.environ.get("TOTEMD_BUS_URL", "http://127.0.0.1:8081/bus"),
    )
    parser.add_argument(
        "--runtime-poll-seconds",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_SNAPSHOT_POLL_SECONDS", "15")),
    )
    parser.add_argument(
        "--runtime-reconnect-seconds",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_RECONNECT_SECONDS", "2")),
    )
    parser.add_argument(
        "--caption-word-seconds",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_CAPTION_WORD_SECONDS", "1.2")),
        help="seconds between progressive caption words",
    )
    parser.add_argument(
        "--coalesce-seconds",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_COALESCE_SECONDS", "2.1")),
    )
    parser.add_argument(
        "--low-battery-percent",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_LOW_BATTERY_PERCENT", "20")),
    )
    parser.add_argument(
        "--critical-battery-percent",
        type=float,
        default=float(os.environ.get("TOTEM_SCREEN_CRITICAL_BATTERY_PERCENT", "8")),
    )
    parser.add_argument(
        "--sequence-rate",
        action="append",
        default=[
            value.strip()
            for value in os.environ.get("TOTEM_SCREEN_SEQUENCE_RATES", "").split(",")
            if value.strip()
        ],
        metavar="SCENE=SECONDS",
        help="override a scene's per-frame interval; repeat for multiple scenes",
    )
    parser.add_argument(
        "--scene-dwell",
        action="append",
        default=[
            value.strip()
            for value in os.environ.get("TOTEM_SCREEN_SCENE_DWELLS", "").split(",")
            if value.strip()
        ],
        metavar="SCENE=SECONDS",
        help="override a scene's minimum dwell; repeat for multiple scenes",
    )
    parser.add_argument(
        "--scene-priority",
        action="append",
        default=[
            value.strip()
            for value in os.environ.get("TOTEM_SCREEN_SCENE_PRIORITIES", "").split(",")
            if value.strip()
        ],
        metavar="SCENE=INTEGER",
        help="override scene arbitration priority; repeat for multiple scenes",
    )
    parser.add_argument(
        "--maximum-pending-scenes",
        type=int,
        default=int(os.environ.get("TOTEM_SCREEN_MAX_PENDING_SCENES", "8")),
    )
    parser.add_argument(
        "--replay-frame-seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--atlas-output",
        help="PNG contact sheet written by replay or caption proof commands",
    )
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
    policy = RuntimePolicy(
        low_battery_percent=args.low_battery_percent,
        critical_battery_percent=args.critical_battery_percent,
        coalesce_seconds=args.coalesce_seconds,
        snapshot_poll_seconds=args.runtime_poll_seconds,
        reconnect_seconds=args.runtime_reconnect_seconds,
        caption_word_seconds=args.caption_word_seconds,
        maximum_pending_scenes=args.maximum_pending_scenes,
    )
    policy = (
        policy.with_frame_rates(args.sequence_rate)
        .with_minimum_dwells(args.scene_dwell)
        .with_priorities(args.scene_priority)
    )
    bus = TotemdBus(args.totemd_bus_url)
    snapshots = TotemSnapshotClient(bus, display)
    runtime = RuntimeController(display, renderer, policy)

    if args.command in ("replay-states", "replay-all-states", "proof-captions"):
        try:
            snapshot = await snapshots.fetch()
        except SnapshotUnavailable:
            snapshot = synthetic_snapshot(
                os.environ.get("TOTEM_SCREEN_DEVICE_NAME", "TOTEM")
            )
        if args.command == "proof-captions":
            runtime.render_caption_proof(snapshot, atlas_output=args.atlas_output)
        else:
            await runtime.replay_all_states(
                snapshot,
                frame_seconds=args.replay_frame_seconds,
                atlas_output=args.atlas_output,
            )
        return

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
        source = RuntimeSource(
            snapshots,
            stream_factory=lambda: TotemdEventStream(bus_address=bus.event_address),
            poll_seconds=policy.snapshot_poll_seconds,
            reconnect_seconds=policy.reconnect_seconds,
        )
        await runtime.run(source, stop)


def main() -> None:
    args = _parser().parse_args()
    setup_logger(level=getattr(logging, args.log_level.upper()))
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
