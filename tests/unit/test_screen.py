import asyncio
import socket
import tempfile

from PIL import Image, ImageChops
import pytest

from totem.screen.controller import ScreenController
from totem.screen.model import ScreenFrame, ScreenState
from totem.screen.readiness import (
    SERVICE_SPECS,
    SyntheticReadinessMonitor,
    statuses,
)
from totem.screen.render import FrameRenderer
from totem.screen.systemd import SystemdNotifier

pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class FakeDisplay:
    def __init__(self):
        self.waited = False
        self.images = []

    async def wait_ready(self, timeout=60.0):
        self.waited = True

    async def show(self, image):
        self.images.append(image.copy())


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def ready(self, status="Boot splash rendered"):
        self.calls.append(status)
        return True


def _ink_bounds(image: Image.Image):
    background = Image.new("1", image.size, 255)
    return ImageChops.difference(image, background).getbbox()


def test_splash_is_large_and_centered():
    renderer = FrameRenderer()
    image = renderer.render(ScreenFrame(ScreenState.BOOTING, "TOTEM"))
    bounds = _ink_bounds(image)

    assert image.size == (250, 122)
    assert bounds is not None
    left, top, right, bottom = bounds
    assert right - left >= 100
    # Font rasterization varies by a pixel across Pillow/platform builds.
    assert abs((left + right) / 2 - image.width / 2) <= 3
    assert abs((top + bottom) / 2 - image.height / 2) <= 3


def test_service_frame_changes_when_a_checkmark_appears():
    renderer = FrameRenderer()
    waiting = renderer.render(
        ScreenFrame(ScreenState.BOOTING, "STARTING", statuses(set()))
    )
    ready = renderer.render(
        ScreenFrame(ScreenState.BOOTING, "STARTING", statuses({"device"}))
    )

    assert ImageChops.difference(waiting, ready).getbbox() is not None


def test_renderer_applies_device_mount_rotation():
    upright = FrameRenderer().render(ScreenFrame(ScreenState.BOOTING, "TOTEM"))
    mounted = FrameRenderer(rotation=180).render(
        ScreenFrame(ScreenState.BOOTING, "TOTEM")
    )

    assert mounted.tobytes() == upright.rotate(180).tobytes()


def test_systemd_notifier_releases_boot_order_after_splash():
    with tempfile.TemporaryDirectory(prefix="totem-", dir="/tmp") as directory:
        address = f"{directory}/notify.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
            server.bind(address)
            server.settimeout(1)

            assert SystemdNotifier(address).ready()
            assert server.recv(256) == b"READY=1\nSTATUS=Boot splash rendered"


def test_synthetic_boot_replays_every_transition(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    display = FakeDisplay()
    notifier = FakeNotifier()
    controller = ScreenController(display, FrameRenderer())

    asyncio.run(
        controller.boot(
            SyntheticReadinessMonitor(),
            notifier,
            poll_interval=0.1,
            settle_seconds=2.0,
        )
    )

    assert display.waited
    assert notifier.calls == ["Boot splash rendered"]
    assert len(display.images) == 3 + len(SERVICE_SPECS)
    assert controller.current == ScreenFrame(ScreenState.IDLE, "(^_^)")
    assert sleeps[-1] == 2.0
