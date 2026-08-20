"""Bluetooth/BLE driver contract and selection."""

from abc import abstractmethod
import sys
from pathlib import Path
from typing import Optional

from totem.devices.contracts import DeviceDriver
from totem.devices.registry import DriverRegistry, DriverSpec, HardwareNotFoundError
from totem.logging import logger


class BluetoothDeviceInterface(DeviceDriver):
    @abstractmethod
    def get_radio_state(self):
        pass

    @abstractmethod
    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        pass

    @abstractmethod
    def get_capabilities(self):
        pass

    @abstractmethod
    def start_discovery(
        self,
        duration_seconds: int = 30,
        service_uuids=None,
        duplicate_data: bool = True,
        session_id=None,
        timeout: float = 15.0,
    ):
        pass

    @abstractmethod
    def stop_discovery(self, session_id: str, timeout: float = 15.0):
        pass

    @abstractmethod
    def discovery_session_count(self) -> int:
        pass

    @abstractmethod
    def list_devices(self):
        pass

    @abstractmethod
    def register_advertisement(self, specification, timeout: float = 15.0):
        pass

    @abstractmethod
    def unregister_advertisement(self, advertisement_id: str, timeout: float = 15.0):
        pass

    @abstractmethod
    def list_advertisements(self):
        pass

    @abstractmethod
    def connect_device(self, device_id: str, timeout: float = 30.0):
        pass

    @abstractmethod
    def disconnect_device(self, device_id: str, timeout: float = 15.0):
        pass

    @abstractmethod
    def list_gatt(self, device_id: str):
        pass

    @abstractmethod
    def read_characteristic(
        self, device_id: str, characteristic_id: str, timeout: float = 15.0
    ):
        pass

    @abstractmethod
    def write_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        value: bytes,
        with_response: bool = True,
        timeout: float = 15.0,
    ):
        pass

    @abstractmethod
    def subscribe_characteristic(
        self,
        device_id: str,
        characteristic_id: str,
        subscription_id=None,
        timeout: float = 15.0,
    ):
        pass

    @abstractmethod
    def unsubscribe_characteristic(self, subscription_id: str, timeout: float = 15.0):
        pass


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
