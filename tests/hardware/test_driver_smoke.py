"""Opt-in initialization checks for an assembled Totem device."""

import os

import pytest


pytestmark = pytest.mark.hardware


def _selected(component):
    configured = os.environ.get(
        "TOTEM_HARDWARE_COMPONENTS", "display,nfc,network,storage"
    )
    return component in {value.strip() for value in configured.split(",")}


def test_display_driver_initializes():
    if not _selected("display"):
        pytest.skip("display excluded by TOTEM_HARDWARE_COMPONENTS")
    driver_name = os.environ.get("TOTEM_EINK_DRIVER")
    if not driver_name:
        pytest.skip("TOTEM_EINK_DRIVER must identify the attached panel")

    from totem.devices.display.display import EInk

    display = EInk(driver_name)
    display.initialize()
    assert display.driver.health().operational


def test_nfc_driver_initializes():
    if not _selected("nfc"):
        pytest.skip("nfc excluded by TOTEM_HARDWARE_COMPONENTS")

    from totem.devices.nfc.nfc import NFC

    nfc = NFC(os.environ.get("TOTEM_NFC_DRIVER"))
    nfc.initialize()
    assert nfc.driver.health().operational


def test_network_driver_initializes():
    if not _selected("network"):
        pytest.skip("network excluded by TOTEM_HARDWARE_COMPONENTS")

    from totem.devices.network.network import WiFi

    wifi = WiFi(os.environ.get("TOTEM_WIFI_DRIVER"))
    wifi.initialize()
    assert wifi.driver.health().operational


def test_storage_driver_initializes():
    if not _selected("storage"):
        pytest.skip("storage excluded by TOTEM_HARDWARE_COMPONENTS")

    from totem.devices.storage.drivers.generic_nvme import Driver

    driver = Driver(root=os.environ.get("TOTEM_STORAGE_ROOT", "/mnt/nvme"))
    assert driver.init() is True
    assert driver.health().operational
