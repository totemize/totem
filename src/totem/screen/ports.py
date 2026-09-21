"""Narrow screen-domain ports for capability-oriented hardware access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from PIL import Image


@dataclass(frozen=True)
class HardwareHealthSnapshot:
    """Stable readiness values the screen can safely render or retry."""

    ready: bool
    degraded: bool


@dataclass(frozen=True)
class PowerSnapshot:
    """Only the power telemetry values useful to screen presentation."""

    battery_percent: Optional[float]
    power_plugged: Optional[bool]


class FrameSink(Protocol):
    """Accept complete monochrome frames after screen-owned rendering."""

    async def wait_ready(self, timeout: float = 60.0) -> None:
        """Wait until the selected frame sink is ready for a frame."""

    async def show(self, image: Image.Image) -> None:
        """Submit one fully rendered frame."""


class HardwareHealth(Protocol):
    """Read the redacted hardware status required for screen boot progress."""

    async def snapshot(self) -> HardwareHealthSnapshot:
        """Return the current hardware readiness without runtime internals."""


class PowerStatus(Protocol):
    """Read the optional presentation-level power state."""

    async def snapshot(self) -> PowerSnapshot:
        """Return only bounded power values used by the screen."""
