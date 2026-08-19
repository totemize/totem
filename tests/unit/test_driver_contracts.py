"""Contract tests shared by every loadable Totem device driver."""

import importlib
import inspect

import pytest
from PIL import Image

from totem.devices.contracts import DeviceDriver, DriverState
from totem.devices.display.display import EInkDeviceInterface
from totem.devices.nfc.nfc import NFCDeviceInterface
from totem.devices.storage.device import StorageDeviceInterface
from totem.devices.network.network import WiFiDeviceInterface


pytestmark = pytest.mark.unit


DRIVERS = (
    ("totem.devices.display.drivers.mock_eink", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v1", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v2", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v3", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_v4", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_pi5", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13_pi5_sw_cs", EInkDeviceInterface),
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

    assert issubclass(driver_class, DeviceDriver)
    assert issubclass(driver_class, interface)
    assert not inspect.isabstract(driver_class)

    for method_name in interface.__abstractmethods__:
        _assert_compatible_signature(
            getattr(interface, method_name),
            getattr(driver_class, method_name),
        )


@pytest.mark.parametrize(
    "module_name",
    (
        "totem.devices.display.drivers.mock_eink",
        "totem.devices.nfc.drivers.mock_nfc",
        "totem.devices.network.drivers.mock_wifi",
    ),
)
def test_mock_driver_reports_mock_health(module_name):
    driver = importlib.import_module(module_name).Driver()

    assert driver.health().state == DriverState.NEW
    driver.init()
    assert driver.health().state == DriverState.MOCK
    assert driver.health().operational
    driver.close()
    assert driver.health().state == DriverState.CLOSED


def test_waveshare_2in13_v4_uses_native_framebuffer_geometry():
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
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


def test_waveshare_2in13_v2_uses_rev_2_1_pixel_mapping():
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

    class FakeGPIO:
        BCM = 0
        OUT = 2
        IN = 3
        HIGH = 1
        LOW = 0

        @staticmethod
        def setwarnings(enabled):
            pass

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setup(pin, mode):
            pass

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

    monkeypatch.setattr(
        "totem.devices.display.drivers._waveshare_2in13_base.time.sleep",
        lambda _: None,
    )
    driver = module.Driver()
    driver.GPIO = FakeGPIO
    driver.SPI = FakeSPI()
    driver.hardware_available = True

    driver.init()
    assert (driver.power_pin, FakeGPIO.HIGH) in outputs
    driver.close()
    assert outputs[-1] == (driver.power_pin, FakeGPIO.LOW)
