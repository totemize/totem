"""Contract tests shared by every loadable Totem device driver."""

import importlib
import inspect

import pytest
from PIL import Image

from totem.devices.contracts import DeviceDriver, DriverHealth, DriverState
from totem.devices.display.display import EInkDeviceInterface
from totem.devices.nfc.nfc import NFCDeviceInterface
from totem.devices.storage.device import StorageDeviceInterface
from totem.devices.network.network import WiFiDeviceInterface
from totem.devices.network.bluetooth import BluetoothDeviceInterface
from totem.devices.ups.ups import UPSDeviceInterface
from totem_driver_api import BindingState


pytestmark = pytest.mark.unit


DRIVERS = (
    ("totem.devices.display.drivers.mock_eink", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v1", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v2", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v3", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v4", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_pi5", EInkDeviceInterface),
    (
        "totem.devices.display.drivers.waveshare_2in13_pi5_sw_cs",
        EInkDeviceInterface,
    ),
    ("totem.devices.display.drivers.waveshare_3in7", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_3in7_pi5", EInkDeviceInterface),
    ("totem.devices.nfc.drivers.acr122", NFCDeviceInterface),
    ("totem.devices.nfc.drivers.pn532", NFCDeviceInterface),
    ("totem.devices.nfc.drivers.mock_nfc", NFCDeviceInterface),
    ("totem.devices.storage.drivers.filesystem", StorageDeviceInterface),
    ("totem.devices.storage.drivers.generic_nvme", StorageDeviceInterface),
    ("totem.devices.network.drivers.mock_wifi", WiFiDeviceInterface),
    ("totem.devices.network.drivers.rpi5_onboard_wifi", WiFiDeviceInterface),
    ("totem.devices.network.drivers.usb_wifi_adapter", WiFiDeviceInterface),
    ("totem.devices.network.drivers.bluez", BluetoothDeviceInterface),
    ("totem.devices.network.drivers.mock_bluetooth", BluetoothDeviceInterface),
    ("totem.devices.ups.drivers.pisugar2", UPSDeviceInterface),
    ("totem.devices.ups.drivers.waveshare_ups_hat_c", UPSDeviceInterface),
)


def _assert_compatible_signature(contract_method, implementation_method):
    contract = inspect.signature(contract_method)
    implementation = inspect.signature(implementation_method)
    positional = [
        object()
        for parameter in contract.parameters.values()
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    implementation.bind(*positional)


@pytest.mark.parametrize(("module_name", "interface"), DRIVERS)
def test_driver_implements_declared_contract(module_name, interface):
    driver_class = importlib.import_module(module_name).Driver

    assert not inspect.isabstract(driver_class)

    for method_name in interface.__abstractmethods__:
        _assert_compatible_signature(
            getattr(interface, method_name),
            getattr(driver_class, method_name),
        )


def test_legacy_lifecycle_names_project_the_explicit_public_contract() -> None:
    health = DriverHealth(state=BindingState.READY)

    assert DriverState is BindingState
    assert health.operational is True
    assert DriverHealth(state=BindingState.CLOSED).operational is False
    assert not hasattr(DeviceDriver, "health")
    assert not hasattr(DeviceDriver, "close")


def test_waveshare_2in13_v4_uses_native_framebuffer_geometry():
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    sleeps = []
    driver = Driver(sleep=sleeps.append)
    white = driver.getbuffer(Image.new("1", (250, 122), 255))
    image = Image.new("1", (250, 122), 255)
    image.putpixel((0, 0), 0)
    with_black_pixel = driver.getbuffer(image)

    assert len(white) == Driver.FRAME_BYTES == 4_000
    # The native width is 122 pixels: each row has 15 full white bytes and
    # two ignored padding bits in its final byte.
    assert white[: Driver.LINE_BYTES] == bytes([0xFF] * 15 + [0xC0])
    assert with_black_pixel != white
    driver.close()


def test_waveshare_2in13_v2_uses_landscape_pixel_mapping():
    from totem.devices.display.drivers.waveshare_2in13_v2 import Driver

    driver = Driver()
    white = driver.getbuffer(Image.new("1", (250, 122), 255))
    image = Image.new("1", (250, 122), 255)
    image.putpixel((0, 0), 0)
    with_black_pixel = driver.getbuffer(image)

    assert len(white) == Driver.FRAME_BYTES == 4_000
    assert set(white) == {0xFF}
    assert with_black_pixel[0] == 0x7F
    driver.close()


def test_waveshare_2in13_legacy_name_aliases_v2():
    from totem.devices.display.drivers.waveshare_2in13 import Driver as Legacy
    from totem.devices.display.drivers.waveshare_2in13_v2 import Driver as V2

    assert Legacy is V2


def test_waveshare_2in13_v4_busy_is_active_high():
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    readings = iter((1, 1, 0))

    class BusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return next(readings)

    driver.GPIO = BusyGPIO
    driver.wait_until_idle(timeout=1, poll_interval=0)


def test_waveshare_2in13_v4_busy_wait_is_bounded():
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()

    class StuckBusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return 1

    driver.GPIO = StuckBusyGPIO
    with pytest.raises(TimeoutError, match="BUSY remained high"):
        driver.wait_until_idle(timeout=0, poll_interval=0)


def test_waveshare_2in13_refresh_requires_busy_assertion():
    from totem.devices.display.drivers.waveshare_2in13_v3 import Driver

    driver = Driver()

    class FloatingBusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return 0

    driver.GPIO = FloatingBusyGPIO
    with pytest.raises(TimeoutError, match="BUSY did not assert"):
        driver.wait_until_idle(
            poll_interval=0,
            require_busy=True,
            busy_assert_timeout=0,
        )
    assert driver.last_refresh_confirmed_by_busy is False


def test_waveshare_2in13_required_busy_cycle_records_confirmation():
    from totem.devices.display.drivers.waveshare_2in13_v2 import Driver

    driver = Driver()
    readings = iter((1, 1, 0))

    class BusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return next(readings)

    driver.GPIO = BusyGPIO
    driver.wait_until_idle(
        timeout=1,
        poll_interval=0,
        require_busy=True,
    )

    assert driver.CONFIRMS_REFRESH_WITH_BUSY is True
    assert driver.last_refresh_confirmed_by_busy is True


def test_waveshare_2in13_v4_waits_for_complete_refresh_cycle(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    commands = []
    data = []
    waits = []
    monkeypatch.setattr(driver, "send_command", commands.append)
    monkeypatch.setattr(driver, "send_data", data.append)
    monkeypatch.setattr(
        driver,
        "wait_for_refresh",
        lambda **kwargs: waits.append(kwargs) or True,
    )

    driver._update()

    assert commands == [
        driver.DISPLAY_UPDATE_CONTROL_2,
        driver.MASTER_ACTIVATION,
    ]
    assert data == [0xF7]
    assert waits == [
        {
            "busy_assert_timeout": driver.BUSY_ASSERT_TIMEOUT_SECONDS,
            "fallback_timeout": driver.REFRESH_FALLBACK_SECONDS,
        }
    ]
    assert driver.last_refresh_confirmed_by_busy is True


def test_waveshare_refresh_wait_catches_late_busy_assertion():
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    sleeps = []
    driver = Driver(sleep=sleeps.append)
    readings = iter((0, 0, 1, 1, 0))

    class BusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return next(readings)

    driver.GPIO = BusyGPIO

    confirmed = driver.wait_for_refresh(
        poll_interval=0,
        busy_assert_timeout=1,
        fallback_timeout=30,
    )

    assert confirmed is True
    assert 30 not in sleeps


def test_waveshare_refresh_wait_holds_power_when_busy_is_not_observed(
    monkeypatch,
):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    sleeps = []
    driver = Driver(sleep=sleeps.append)

    class IdleGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return 0

    driver.GPIO = IdleGPIO

    confirmed = driver.wait_for_refresh(
        busy_assert_timeout=0,
        fallback_timeout=30,
    )

    assert confirmed is False
    assert sleeps == [30]


@pytest.mark.parametrize(
    "module_name",
    (
        "totem.devices.display.drivers.waveshare_2in13_v1",
        "totem.devices.display.drivers.waveshare_2in13_v2",
        "totem.devices.display.drivers.waveshare_2in13_v3",
        "totem.devices.display.drivers.waveshare_2in13_v4",
    ),
)
def test_waveshare_2in13_controls_hat_power(monkeypatch, module_name):
    module = importlib.import_module(module_name)

    outputs = []
    setup_calls = []

    class FakeGPIO:
        BCM = 0
        OUT = 2
        IN = 3
        HIGH = 1
        LOW = 0
        PUD_DOWN = 21

        @staticmethod
        def setwarnings(enabled):
            pass

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setup(pin, mode, **kwargs):
            setup_calls.append((pin, mode, kwargs))

        @staticmethod
        def output(pin, value):
            outputs.append((pin, value))

        @staticmethod
        def input(pin):
            return 0

        @staticmethod
        def cleanup(pin):
            pass

    class FakeSPI:
        def open(self, bus, device):
            pass

        def writebytes(self, data):
            pass

        def close(self):
            pass

    driver = module.Driver(sleep=lambda _: None)
    driver.GPIO = FakeGPIO
    driver.SPI = FakeSPI()
    driver.hardware_available = True

    driver.init()
    assert (driver.power_pin, FakeGPIO.HIGH) in outputs
    assert (
        driver.busy_pin,
        FakeGPIO.IN,
        {"pull_up_down": FakeGPIO.PUD_DOWN},
    ) in setup_calls
    driver.close()
    assert outputs[-1] == (driver.power_pin, FakeGPIO.LOW)
