from unittest.mock import patch

import pytest

from devices.nfc.nfc import NFC, NFC_DRIVERS
from devices.registry import HardwareNotFoundError, MockDriverNotAllowedError
from devices.wifi.wifi import WIFI_DRIVERS, WiFi


def test_nfc_registry_uses_case_safe_module_names():
    assert NFC_DRIVERS.names == ("acr122", "mock_nfc", "pn532")
    assert type(NFC("acr122").driver).__module__.endswith(".ACR122")
    assert type(NFC("pn532").driver).__module__.endswith(".PNC532")


def test_nfc_usb_detection_parses_lsusb_output():
    output = b"Bus 001 Device 004: ID 04e6:5591 SCM Microsystems Inc.\n"
    with patch("devices.nfc.nfc.sys.platform", "linux"), patch(
        "devices.nfc.nfc.subprocess.check_output", return_value=output
    ):
        assert NFC().driver.__class__.__module__.endswith(".ACR122")


def test_wifi_registry_uses_existing_module_names():
    assert WIFI_DRIVERS.names == (
        "mock_wifi",
        "rpi5_onboard_wifi",
        "usb_wifi_adapter",
    )
    assert type(WiFi("rpi5_onboard_wifi").driver).__module__.endswith(
        ".rpi5_onboard_wifi"
    )


def test_wifi_detection_resolves_onboard_driver():
    with patch("devices.wifi.wifi.sys.platform", "linux"), patch(
        "devices.wifi.wifi.subprocess.check_output", return_value=b"lo\nwlan0\n"
    ):
        assert WiFi().driver.__class__.__module__.endswith(".rpi5_onboard_wifi")


@pytest.mark.parametrize(
    ("factory", "mock_name"),
    ((NFC, "mock_nfc"), (WiFi, "mock_wifi")),
)
def test_mock_drivers_require_explicit_permission(factory, mock_name):
    with pytest.raises(MockDriverNotAllowedError):
        factory(mock_name)

    assert factory(mock_name, allow_mock=True).driver.is_mock


@pytest.mark.parametrize("factory", (NFC, WiFi))
def test_detection_failure_does_not_fall_back_to_mock(factory):
    with patch.object(factory, "_detect_hardware", return_value=None):
        with pytest.raises(HardwareNotFoundError):
            factory()


@pytest.mark.parametrize(
    ("factory", "expected_module"),
    ((NFC, "mock_nfc"), (WiFi, "mock_wifi")),
)
def test_detection_failure_allows_explicit_mock(factory, expected_module):
    with patch.object(factory, "_detect_hardware", return_value=None):
        driver = factory(allow_mock=True).driver
    assert driver.is_mock
    assert driver.__class__.__module__.endswith("." + expected_module)
