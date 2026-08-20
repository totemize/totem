"""Contract tests shared by every loadable Totem device driver."""

import importlib
import inspect
import sys
from types import ModuleType

import pytest
from PIL import Image

from totem.devices.contracts import DeviceDriver, DriverState
from totem.devices.display.display import EInkDeviceInterface
from totem.devices.nfc.nfc import NFCDeviceInterface
from totem.devices.storage.device import StorageDeviceInterface
from totem.devices.network.network import WiFiDeviceInterface
from totem.devices.ups.ups import UPSDeviceInterface


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


def test_waveshare_2in13_v4_full_refresh_seeds_both_ram_planes(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    driver.initialized = True
    payload = bytes([0xA5]) * driver.FRAME_BYTES
    events = []
    monkeypatch.setattr(
        driver, "send_command", lambda value: events.append(("cmd", value))
    )
    monkeypatch.setattr(
        driver, "send_data", lambda value: events.append(("data", value))
    )
    monkeypatch.setattr(
        driver, "_prepare_frame_write", lambda: events.append(("prepare",))
    )
    monkeypatch.setattr(driver, "_update", lambda: events.append(("update",)))

    driver.display_bytes(payload)

    assert events == [
        ("cmd", driver.BORDER_WAVEFORM_CONTROL),
        ("data", driver.FULL_BORDER_WAVEFORM),
        ("prepare",),
        ("cmd", driver.WRITE_RAM),
        ("data", payload),
        ("cmd", driver.WRITE_RAM_PREVIOUS),
        ("data", payload),
        ("update",),
    ]
    assert driver._previous_frame == payload
    assert driver.partial_refresh_ready is True


def test_waveshare_2in13_v4_partial_refresh_uses_differential_sequence(
    monkeypatch,
):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    driver.initialized = True
    previous = bytes([0xFF]) * driver.FRAME_BYTES
    payload = bytes([0x00]) * driver.FRAME_BYTES
    driver._previous_frame = previous
    events = []

    class FakeGPIO:
        HIGH = 1
        LOW = 0

        @staticmethod
        def output(pin, value):
            events.append(("gpio", pin, value))

    driver.GPIO = FakeGPIO
    monkeypatch.setattr(
        "totem.devices.display.drivers.waveshare_2in13_v4.time.sleep",
        lambda value: events.append(("sleep", value)),
    )
    monkeypatch.setattr(
        driver, "send_command", lambda value: events.append(("cmd", value))
    )
    monkeypatch.setattr(
        driver, "send_data", lambda value: events.append(("data", value))
    )
    monkeypatch.setattr(
        driver, "_prepare_frame_write", lambda: events.append(("prepare",))
    )
    monkeypatch.setattr(driver, "_update_partial", lambda: events.append(("partial",)))

    driver.display_bytes_partial(payload)

    assert events == [
        ("gpio", driver.reset_pin, FakeGPIO.LOW),
        ("sleep", driver.PARTIAL_RESET_SECONDS),
        ("gpio", driver.reset_pin, FakeGPIO.HIGH),
        ("cmd", driver.BORDER_WAVEFORM_CONTROL),
        ("data", driver.PARTIAL_BORDER_WAVEFORM),
        ("cmd", driver.DRIVER_OUTPUT_CONTROL),
        ("data", 0xF9),
        ("data", 0x00),
        ("data", 0x00),
        ("cmd", driver.DATA_ENTRY_MODE_SETTING),
        ("data", 0x03),
        ("prepare",),
        ("cmd", driver.WRITE_RAM_PREVIOUS),
        ("data", previous),
        ("cmd", driver.WRITE_RAM),
        ("data", payload),
        ("partial",),
    ]
    assert driver._previous_frame == payload
    assert driver._partial_mode_active is True


def test_waveshare_2in13_v4_resets_only_when_entering_partial_burst(
    monkeypatch,
):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    driver.initialized = True
    driver._previous_frame = bytes([0xFF]) * driver.FRAME_BYTES
    outputs = []

    class FakeGPIO:
        HIGH = 1
        LOW = 0

        @staticmethod
        def output(pin, value):
            outputs.append((pin, value))

    driver.GPIO = FakeGPIO
    monkeypatch.setattr(
        "totem.devices.display.drivers.waveshare_2in13_v4.time.sleep",
        lambda _: None,
    )
    monkeypatch.setattr(driver, "send_command", lambda _: None)
    monkeypatch.setattr(driver, "send_data", lambda _: None)
    monkeypatch.setattr(driver, "_prepare_frame_write", lambda: None)
    monkeypatch.setattr(driver, "_update_partial", lambda: None)

    driver.display_bytes_partial(bytes([0xAA]) * driver.FRAME_BYTES)
    driver.display_bytes_partial(bytes([0x55]) * driver.FRAME_BYTES)

    assert outputs == [
        (driver.reset_pin, FakeGPIO.LOW),
        (driver.reset_pin, FakeGPIO.HIGH),
    ]


def test_waveshare_2in13_v4_partial_update_control_and_busy_wait(monkeypatch):
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

    driver._update_partial()

    assert commands == [
        driver.DISPLAY_UPDATE_CONTROL_2,
        driver.MASTER_ACTIVATION,
    ]
    assert data == [driver.PARTIAL_UPDATE_CONTROL]
    assert waits == [
        {
            "busy_assert_timeout": driver.BUSY_ASSERT_TIMEOUT_SECONDS,
            "fallback_timeout": driver.REFRESH_FALLBACK_SECONDS,
        }
    ]


def test_waveshare_2in13_v4_partial_error_forces_new_full_baseline(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    driver.initialized = True
    driver._previous_frame = bytes([0xFF]) * driver.FRAME_BYTES
    driver._partial_mode_active = True
    monkeypatch.setattr(driver, "send_command", lambda _: None)
    monkeypatch.setattr(driver, "send_data", lambda _: None)
    monkeypatch.setattr(driver, "_prepare_frame_write", lambda: None)
    monkeypatch.setattr(
        driver,
        "_update_partial",
        lambda: (_ for _ in ()).throw(TimeoutError("busy")),
    )

    with pytest.raises(TimeoutError, match="busy"):
        driver.display_bytes_partial(bytes([0x00]) * driver.FRAME_BYTES)

    assert driver._previous_frame is None
    assert driver._partial_mode_active is False


@pytest.mark.parametrize("operation", ("full", "partial"))
def test_waveshare_2in13_v4_early_io_error_invalidates_partial_baseline(
    monkeypatch,
    operation,
):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    driver.initialized = True
    driver._previous_frame = bytes([0xFF]) * driver.FRAME_BYTES
    driver._partial_mode_active = True
    monkeypatch.setattr(
        driver,
        "send_command",
        lambda _: (_ for _ in ()).throw(OSError("spi")),
    )

    with pytest.raises(OSError, match="spi"):
        if operation == "full":
            driver.display_bytes(bytes([0xAA]) * driver.FRAME_BYTES)
        else:
            driver.display_bytes_partial(bytes([0xAA]) * driver.FRAME_BYTES)

    assert driver._previous_frame is None
    assert driver._partial_mode_active is False


def test_waveshare_2in13_v4_partial_rejects_bad_frame_before_io(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    commands = []
    monkeypatch.setattr(driver, "send_command", commands.append)

    with pytest.raises(ValueError, match="Incorrect framebuffer size"):
        driver.display_bytes_partial(b"short")

    assert commands == []


def test_waveshare_refresh_wait_catches_late_busy_assertion(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    driver = Driver()
    readings = iter((0, 0, 1, 1, 0))

    class BusyGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return next(readings)

    sleeps = []
    driver.GPIO = BusyGPIO
    monkeypatch.setattr(
        "totem.devices.display.drivers._waveshare_2in13_base.time.sleep",
        sleeps.append,
    )

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

    driver = Driver()

    class IdleGPIO:
        HIGH = 1

        @staticmethod
        def input(pin):
            return 0

    sleeps = []
    driver.GPIO = IdleGPIO
    monkeypatch.setattr(
        "totem.devices.display.drivers._waveshare_2in13_base.time.sleep",
        sleeps.append,
    )

    confirmed = driver.wait_for_refresh(
        busy_assert_timeout=0,
        fallback_timeout=30,
    )

    assert confirmed is False
    assert sleeps == [30]


def test_gpiozero_facade_claims_drives_reads_and_releases_pins(monkeypatch):
    from totem.devices.display.drivers._waveshare_2in13_base import GPIOZeroGPIO

    events = []

    class FakeDevice:
        def __init__(self, pin, **kwargs):
            self.pin = pin
            self.value = 1
            events.append(("claim", pin, kwargs))

        def on(self):
            events.append(("on", self.pin))

        def off(self):
            events.append(("off", self.pin))

        def close(self):
            events.append(("close", self.pin))

    gpiozero = ModuleType("gpiozero")
    gpiozero.LED = FakeDevice
    gpiozero.Button = FakeDevice
    gpiozero.DigitalInputDevice = FakeDevice
    monkeypatch.setitem(sys.modules, "gpiozero", gpiozero)

    gpio = GPIOZeroGPIO()
    gpio.setup(17, gpio.OUT)
    gpio.output(17, gpio.HIGH)
    gpio.output(17, gpio.LOW)
    gpio.setup(24, gpio.IN, pull_up_down=gpio.PUD_DOWN)

    assert gpio.input(24) == 1
    gpio.cleanup()
    assert ("claim", 24, {"pull_up": False}) in events
    assert ("on", 17) in events
    assert ("off", 17) in events
    assert ("close", 17) in events
    assert ("close", 24) in events


def test_gpiozero_claim_failure_falls_back_to_rpi_gpio(monkeypatch):
    from totem.devices.display.drivers.waveshare_2in13_v4 import Driver

    class FailingGPIO:
        BCM = 0
        OUT = 2
        IN = 3
        HIGH = 1
        PUD_DOWN = 21

        def __init__(self):
            self.cleaned = False

        @staticmethod
        def setwarnings(enabled):
            pass

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setup(pin, mode, **kwargs):
            raise RuntimeError("gpiochip unavailable")

        def cleanup(self):
            self.cleaned = True

    class WorkingGPIO:
        BCM = 0
        OUT = 2
        IN = 3
        HIGH = 1
        LOW = 0
        PUD_DOWN = 21

        def __init__(self):
            self.outputs = []

        @staticmethod
        def setwarnings(enabled):
            pass

        @staticmethod
        def setmode(mode):
            pass

        @staticmethod
        def setup(pin, mode, **kwargs):
            pass

        def output(self, pin, value):
            self.outputs.append((pin, value))

        @staticmethod
        def cleanup(pin=None):
            pass

    class FakeSPI:
        def __init__(self):
            self.opened = None

        def open(self, bus, device):
            self.opened = (bus, device)

        @staticmethod
        def close():
            pass

    failing = FailingGPIO()
    fallback = WorkingGPIO()
    spi = FakeSPI()
    driver = Driver()
    driver.GPIO = failing
    driver.gpio_backend = "gpiozero"
    driver.SPI = spi
    driver.hardware_available = True
    monkeypatch.setattr(driver, "_load_rpi_gpio", lambda: fallback)

    driver._initialize_transport()

    assert failing.cleaned is True
    assert driver.GPIO is fallback
    assert driver.gpio_backend == "RPi.GPIO"
    assert (driver.power_pin, fallback.HIGH) in fallback.outputs
    assert spi.opened == (0, 0)


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
    assert (
        driver.busy_pin,
        FakeGPIO.IN,
        {"pull_up_down": FakeGPIO.PUD_DOWN},
    ) in setup_calls
    driver.close()
    assert outputs[-1] == (driver.power_pin, FakeGPIO.LOW)
