from abc import abstractmethod
import re
import sys
import subprocess
from typing import Optional
from utils.logger import logger
from devices.contracts import DeviceDriver
from devices.registry import (
    DriverRegistry,
    DriverSpec,
    HardwareNotFoundError,
)

class NFCDeviceInterface(DeviceDriver):
    @abstractmethod
    def init(self):
        """Initialize the NFC device."""
        pass

    @abstractmethod
    def read(self) -> bytes:
        """Read data from the NFC device."""
        pass

    @abstractmethod
    def write(self, data: bytes):
        """Write data to the NFC device."""
        pass


NFC_DRIVERS = DriverRegistry(
    NFCDeviceInterface,
    (
        DriverSpec("acr122", "devices.nfc.drivers.ACR122"),
        DriverSpec("pn532", "devices.nfc.drivers.PNC532"),
        DriverSpec("mock_nfc", "devices.nfc.drivers.mock_nfc", is_mock=True),
    ),
)

class NFC:
    def __init__(
        self, driver_name: Optional[str] = None, *, allow_mock: bool = False
    ):
        self.allow_mock = allow_mock
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            elif allow_mock:
                logger.warning("No hardware detected; explicit mock mode is enabled.")
                self.driver = self._load_driver_by_name('mock_nfc')
            else:
                raise HardwareNotFoundError("No supported NFC hardware detected")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting NFC hardware...")
        
        # For non-Linux systems, don't attempt to use lsusb
        if not sys.platform.startswith('linux'):
            logger.info(f"NFC probing is unavailable on {sys.platform}")
            return None
            
        try:
            output = subprocess.check_output(['lsusb']).decode('utf-8')
            logger.debug(f"lsusb output:\n{output}")
        except Exception as e:
            logger.error(f"Error executing lsusb: {e}")
            return None

        hardware_map = {
            ('04e6', '5591'): 'acr122',
            ('0483', '5740'): 'pn532',
        }

        for line in output.splitlines():
            match = re.search(r"\bID\s+([0-9a-f]{4}):([0-9a-f]{4})\b", line, re.I)
            if not match:
                continue
            driver_name = hardware_map.get(
                (match.group(1).lower(), match.group(2).lower())
            )
            if driver_name:
                logger.info(f"Detected NFC device: {driver_name}")
                return driver_name
        logger.warning("No known NFC hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> NFCDeviceInterface:
        driver = NFC_DRIVERS.load(driver_name, allow_mock=self.allow_mock)
        logger.info(f"Loaded driver: {driver_name}")
        return driver

    def initialize(self):
        self.driver.init()

    def read_data(self) -> bytes:
        return self.driver.read()

    def write_data(self, data: bytes):
        self.driver.write(data)
