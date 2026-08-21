"""Composable state machine for screen presentation."""

import asyncio
from typing import Protocol, Set

from totem.logging import logger
from totem.screen.model import ScreenFrame, ScreenState
from totem.screen.readiness import SERVICE_SPECS, statuses
from totem.screen.render import FrameRenderer


class Display(Protocol):
    async def wait_ready(self, timeout: float = 60.0) -> None: ...

    async def show(self, image, refresh_mode: str = "full") -> None: ...


class ReadinessMonitor(Protocol):
    async def snapshot(self) -> Set[str]: ...


class Notifier(Protocol):
    def ready(self, status: str = "Boot splash rendered") -> bool: ...


class ScreenController:
    def __init__(self, display: Display, renderer: FrameRenderer):
        self.display = display
        self.renderer = renderer
        self.current = ScreenFrame(ScreenState.BOOTING, "TOTEM")
        self._has_drawn = False

    async def transition(self, frame: ScreenFrame) -> None:
        logger.info("Screen transition: %s", frame.state.value)
        await self.display.show(
            self.renderer.render(frame),
            refresh_mode="partial" if self._has_drawn else "full",
        )
        self._has_drawn = True
        self.current = frame

    async def boot(
        self,
        monitor: ReadinessMonitor,
        notifier: Notifier,
        *,
        poll_interval: float = 0.5,
        settle_seconds: float = 2.0,
    ) -> None:
        await self.display.wait_ready()
        await self.transition(ScreenFrame(ScreenState.BOOTING, "TOTEM"))
        notifier.ready()

        ready: Set[str] = set()
        await self.transition(
            ScreenFrame(ScreenState.BOOTING, "STARTING", statuses(ready))
        )

        required = {service.key for service in SERVICE_SPECS}
        while ready != required:
            observed = await monitor.snapshot()
            for service in SERVICE_SPECS:
                if service.key in observed and service.key not in ready:
                    ready.add(service.key)
                    await self.transition(
                        ScreenFrame(
                            ScreenState.BOOTING,
                            "STARTING",
                            statuses(ready),
                        )
                    )
            if ready != required:
                await asyncio.sleep(poll_interval)

        await asyncio.sleep(settle_seconds)
        await self.transition(ScreenFrame(ScreenState.IDLE, "(^_^)"))
