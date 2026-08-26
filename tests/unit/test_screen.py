import asyncio
import socket
import tempfile
from types import SimpleNamespace

from PIL import Image, ImageChops
import pytest

from totem.hardware.hosts.protocol import decode_frame
from totem.screen.adapters.hardware_bus import HardwareBusScreenAdapter, ScreenBusError
from totem.screen.display import DeviceManagerDisplay
from totem.screen.controller import ScreenController
from totem.screen.model import ScreenFrame, ScreenState
from totem.screen.ports import HardwareHealthSnapshot, PowerSnapshot
from totem.screen.readiness import (
    LiveReadinessMonitor,
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


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        import json

        return json.dumps(self._payload).encode("utf-8")


class RecordingBusOpener:
    def __init__(self):
        self.messages = []
        self.fail_code = None

    def open(self, operation, timeout):
        message = decode_frame(operation.data)
        self.messages.append((operation, timeout, message))
        result = {
            "type": "{}.result".format(message["type"]),
            "id": message["id"],
            "ok": self.fail_code is None,
        }
        if self.fail_code is not None:
            result["error"] = {"code": self.fail_code}
        elif message["type"] == "hardware.status.get":
            result["status"] = {"ready": True, "degraded": False}
        elif message["type"] == "power.telemetry.read":
            result["telemetry"] = {
                "battery_percent": 73,
                "power_plugged": True,
            }
        return _Response(result)


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


def test_screen_ports_accept_fake_screen_domain_values():
    health = HardwareHealthSnapshot(ready=True, degraded=False)
    power = PowerSnapshot(battery_percent=73, power_plugged=True)

    assert health.ready is True
    assert health.degraded is False
    assert power.battery_percent == 73
    assert power.power_plugged is True


def test_hardware_bus_adapter_uses_correlated_raw_canonical_messages():
    ids = iter(("frame-request", "health-request", "power-request"))
    adapter = HardwareBusScreenAdapter(request_id_factory=lambda: next(ids))
    opener = RecordingBusOpener()
    adapter._opener = opener

    async def exercise():
        await adapter.show(Image.new("1", (2, 2), 255))
        health = await adapter.health.snapshot()
        power = await adapter.power.snapshot()
        return health, power

    health, power = asyncio.run(exercise())

    assert health == HardwareHealthSnapshot(ready=True, degraded=False)
    assert power == PowerSnapshot(battery_percent=73, power_plugged=True)
    assert [message[2]["type"] for message in opener.messages] == [
        "display.frame.write",
        "hardware.status.get",
        "power.telemetry.read",
    ]
    frame = opener.messages[0][2]
    assert frame["id"] == "frame-request"
    assert frame["frame"] == {
        "attachment_id": "frame-frame-request",
        "width": 2,
        "height": 2,
        "pixel_format": "mono1",
    }
    assert frame["_attachments"] == {"frame-frame-request": b"\xc0\xc0"}
    assert frame["_attachment_media_types"] == {
        "frame-frame-request": "application/octet-stream"
    }
    assert all(operation.full_url == "http://127.0.0.1:8000/bus" for operation, _, _ in opener.messages)


def test_hardware_bus_adapter_maps_stable_bus_errors():
    adapter = HardwareBusScreenAdapter(request_id_factory=lambda: "failed-request")
    opener = RecordingBusOpener()
    opener.fail_code = "binding_unavailable"
    adapter._opener = opener

    with pytest.raises(ScreenBusError, match="binding_unavailable") as raised:
        asyncio.run(adapter.health.snapshot())

    assert raised.value.code == "binding_unavailable"


def test_display_compatibility_name_is_only_a_canonical_bus_adapter():
    assert issubclass(DeviceManagerDisplay, HardwareBusScreenAdapter)


def test_live_readiness_reads_hardware_health_port(monkeypatch):
    class Health:
        async def snapshot(self):
            return HardwareHealthSnapshot(ready=True, degraded=False)

    monitor = LiveReadinessMonitor(Health())
    monkeypatch.setattr(monitor, "_fips_ready", lambda: _ready())
    monkeypatch.setattr(monitor, "_relay_ready", lambda: _ready())
    monkeypatch.setattr(monitor, "_totemd_ready", lambda: _ready())

    assert asyncio.run(monitor.snapshot()) == {"device", "fips", "relay", "totemd"}


async def _ready():
    return True


def test_replay_boot_constructs_only_the_screen_bus_adapter(monkeypatch):
    import totem.screen.__main__ as screen_main

    constructed = []

    class FakeBus:
        def __init__(self, base_url):
            constructed.append(base_url)
            self.health = self
            self.power = self

        async def wait_ready(self, timeout=60.0):
            return None

        async def show(self, _image):
            return None

        async def snapshot(self):
            return HardwareHealthSnapshot(ready=True, degraded=False)

    monkeypatch.setattr(screen_main, "HardwareBusScreenAdapter", FakeBus)
    asyncio.run(
        screen_main._run(
            SimpleNamespace(
                command="replay-boot",
                device_api_url="http://127.0.0.1:8000",
                width=250,
                height=122,
                rotation=0,
                poll_interval=0.0,
                settle_seconds=0.0,
            )
        )
    )

    assert constructed == ["http://127.0.0.1:8000"]


def test_screen_parser_preserves_device_url_and_geometry_environment(monkeypatch):
    import totem.screen.__main__ as screen_main

    monkeypatch.setenv("TOTEM_DEVICE_API_URL", "http://127.0.0.1:9010")
    monkeypatch.setenv("TOTEM_SCREEN_WIDTH", "296")
    monkeypatch.setenv("TOTEM_SCREEN_HEIGHT", "128")
    monkeypatch.setenv("TOTEM_SCREEN_ROTATION", "180")

    args = screen_main._parser().parse_args(["replay-boot"])

    assert args.command == "replay-boot"
    assert args.device_api_url == "http://127.0.0.1:9010"
    assert (args.width, args.height, args.rotation) == (296, 128, 180)
