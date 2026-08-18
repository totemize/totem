"""Opt-in initialization checks for an assembled Totem device."""

import os

import pytest


pytestmark = pytest.mark.hardware


def _selected(component):
    configured = os.environ.get("TOTEM_HARDWARE_COMPONENTS", "display,nfc,wifi,nvme")
    return component in {value.strip() for value in configured.split(",")}


def test_display_driver_initializes():
    if not _selected("display"):
        pytest.skip("display excluded by TOTEM_HARDWARE_COMPONENTS")
    driver_name = os.environ.get("TOTEM_EINK_DRIVER")
    if not driver_name:
        pytest.skip("TOTEM_EINK_DRIVER must identify the attached panel")

    from devices.eink.eink import EInk

    display = EInk(driver_name)
    display.initialize()
    assert display.driver.health().operational


def test_nfc_driver_initializes():
    if not _selected("nfc"):
        pytest.skip("nfc excluded by TOTEM_HARDWARE_COMPONENTS")

    from devices.nfc.nfc import NFC

    nfc = NFC(os.environ.get("TOTEM_NFC_DRIVER"))
    nfc.initialize()
    assert nfc.driver.health().operational


def test_wifi_driver_initializes():
    if not _selected("wifi"):
        pytest.skip("wifi excluded by TOTEM_HARDWARE_COMPONENTS")

    from devices.wifi.wifi import WiFi

    wifi = WiFi(os.environ.get("TOTEM_WIFI_DRIVER"))
    wifi.initialize()
    assert wifi.driver.health().operational


def test_nvme_driver_initializes():
    if not _selected("nvme"):
        pytest.skip("nvme excluded by TOTEM_HARDWARE_COMPONENTS")

    from devices.nvme.drivers.generic_nvme import Driver

    driver = Driver(root=os.environ.get("TOTEM_STORAGE_ROOT", "/mnt/nvme"))
    assert driver.init() is True
    assert driver.health().operational
