"""Bluetooth/BLE driver contract and selection."""

from abc import abstractmethod
import sys
from pathlib import Path
from typing import Optional

from totem.devices.registry import DriverRegistry, DriverSpec, HardwareNotFoundError
from totem.hardware.builtin.radio.network import BluetoothDeviceInterface
from totem.logging import logger


BLUETOOTH_DRIVERS = DriverRegistry(
    BluetoothDeviceInterface,
    (
        DriverSpec("bluez", "totem.devices.network.drivers.bluez"),
        DriverSpec(
            "mock_bluetooth",
            "totem.devices.network.drivers.mock_bluetooth",
            is_mock=True,
        ),
    ),
)


class Bluetooth:
    def __init__(self, driver_name: Optional[str] = None, *, allow_mock: bool = False):
        self.allow_mock = allow_mock
        if driver_name:
            selected = driver_name
        elif self._detect_hardware():
            selected = "bluez"
        elif allow_mock:
            selected = "mock_bluetooth"
        else:
            raise HardwareNotFoundError("No supported Bluetooth controller detected")
        self.driver = BLUETOOTH_DRIVERS.load(selected, allow_mock=allow_mock)
        logger.info("Loaded Bluetooth driver: %s", selected)

    @staticmethod
    def _detect_hardware() -> bool:
        return (
            sys.platform.startswith("linux")
            and Path("/sys/class/bluetooth/hci0").exists()
        )

    def initialize(self):
        self.driver.init()

    def set_event_callback(self, callback) -> None:
        setter = getattr(self.driver, "set_event_callback", None)
        if setter:
            setter(callback)

    def __getattr__(self, name):
        return getattr(self.driver, name)
