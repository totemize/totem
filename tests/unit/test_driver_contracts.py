"""Contract tests shared by every loadable Totem device driver."""

import importlib
import inspect

import pytest

from totem.devices.contracts import DeviceDriver, DriverState
from totem.devices.display.display import EInkDeviceInterface
from totem.devices.nfc.nfc import NFCDeviceInterface
from totem.devices.storage.device import StorageDeviceInterface
from totem.devices.network.network import WiFiDeviceInterface


pytestmark = pytest.mark.unit


DRIVERS = (
    ("totem.devices.display.drivers.mock_eink", EInkDeviceInterface),
    ("totem.devices.display.drivers.waveshare_2in13", EInkDeviceInterface),
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
