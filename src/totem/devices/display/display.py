from abc import abstractmethod
import os
from typing import Optional
from totem.logging import logger
from totem.devices.contracts import DeviceDriver
from totem.devices.registry import (
    DriverRegistry,
    DriverSpec,
    HardwareNotFoundError,
    MockDriverNotAllowedError,
)

# src/devices/eink/eink.py

class EInkDeviceInterface(DeviceDriver):
    @abstractmethod
    def init(self):
        """Initialize the e-ink device."""
        pass

    @abstractmethod
    def clear(self):
        """Clear the e-ink display."""
        pass

    @abstractmethod
    def display_image(self, image):
        """Display an image on the e-ink screen."""
        pass

    @abstractmethod
    def display_bytes(self, image_bytes):
        """Display raw byte data on the e-ink screen."""
        pass


EINK_DRIVERS = DriverRegistry(
    EInkDeviceInterface,
    (
        DriverSpec(
            "waveshare_2in13_v1",
            "totem.devices.display.drivers.waveshare_2in13_v1",
        ),
        # Historical name retained as an alias for the V2 controller driver.
        DriverSpec("waveshare_2in13", "totem.devices.display.drivers.waveshare_2in13"),
        DriverSpec(
            "waveshare_2in13_v2",
            "totem.devices.display.drivers.waveshare_2in13_v2",
        ),
        DriverSpec(
            "waveshare_2in13_v3",
            "totem.devices.display.drivers.waveshare_2in13_v3",
        ),
        DriverSpec(
            "waveshare_2in13_v4",
            "totem.devices.display.drivers.waveshare_2in13_v4",
        ),
        DriverSpec(
            "waveshare_2in13_pi5", "totem.devices.display.drivers.waveshare_2in13_pi5"
        ),
        DriverSpec(
            "waveshare_2in13_pi5_sw_cs",
            "totem.devices.display.drivers.waveshare_2in13_pi5_sw_cs",
        ),
        DriverSpec("waveshare_3in7", "totem.devices.display.drivers.waveshare_3in7"),
        DriverSpec(
            "waveshare_3in7_pi5", "totem.devices.display.drivers.waveshare_3in7_pi5"
        ),
        DriverSpec("mock_eink", "totem.devices.display.drivers.mock_eink", is_mock=True),
    ),
)


class EInk:
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
                self.driver = self._load_driver_by_name("mock_eink")
            else:
                raise HardwareNotFoundError("No supported E-Ink hardware detected")

    def _detect_hardware(self) -> Optional[str]:
        logger.info("Detecting E-Ink hardware...")
        
        # First, check if we're running on a Raspberry Pi 5
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            if 'Raspberry Pi 5' in cpuinfo:
                logger.info("Detected Raspberry Pi 5")
                
                # Now determine which display is connected
                # You can add additional detection logic here if needed
                # For now, we'll use environment variables to specify the display type
                display_type = os.environ.get('EINK_DISPLAY_TYPE', '').lower()
                if display_type == '2in13':
                    logger.info("Using 2.13 inch Pi 5 driver")
                    return 'waveshare_2in13_pi5'
                elif display_type == '3in7':
                    logger.info("Using 3.7 inch Pi 5 driver")
                    return 'waveshare_3in7_pi5'
                else:
                    # Default to 3.7 inch for Pi 5 if not specified
                    logger.info("No specific display type set, defaulting to 3.7 inch Pi 5 driver")
                    return 'waveshare_3in7_pi5'
        except Exception as e:
            logger.error(f"Error checking Raspberry Pi version: {e}")
        
        # Check for SPI devices
        try:
            spi_devices = os.listdir('/dev/')
            spi_devices = [dev for dev in spi_devices if dev.startswith('spidev')]
            logger.debug(f"SPI devices found: {spi_devices}")
            
            if spi_devices:
                # Determine which display is connected on non-Pi 5 systems
                display_type = os.environ.get('EINK_DISPLAY_TYPE', '').lower()
                if display_type == '2in13_v1':
                    logger.info("Using 2.13 inch V1 driver")
                    return 'waveshare_2in13_v1'
                elif display_type in {'2in13', '2in13_v2'}:
                    logger.info("Using 2.13 inch driver")
                    return 'waveshare_2in13_v2'
                elif display_type == '2in13_v3':
                    logger.info("Using 2.13 inch V3 driver")
                    return 'waveshare_2in13_v3'
                elif display_type == '2in13_v4':
                    logger.info("Using 2.13 inch V4 driver")
                    return 'waveshare_2in13_v4'
                elif display_type == '3in7':
                    logger.info("Using 3.7 inch driver")
                    return 'waveshare_3in7'
                else:
                    # Default to 3.7 inch if not specified
                    logger.info("No specific display type set, defaulting to 3.7 inch driver")
                    return 'waveshare_3in7'
        except Exception as e:
            logger.error(f"Error accessing /dev/: {e}")
            return None

        logger.warning("No known E-Ink hardware detected.")
        return None

    def _load_driver_by_name(self, driver_name: str) -> EInkDeviceInterface:
        driver = EINK_DRIVERS.load(driver_name, allow_mock=self.allow_mock)
        logger.info(f"Loaded driver: {driver_name}")
        return driver

    def initialize(self, *args, **kwargs):
        result = self.driver.init(*args, **kwargs)
        if self.driver.is_mock and not self.allow_mock:
            self.driver.close()
            raise MockDriverNotAllowedError(
                "E-Ink hardware initialization selected an implicit mock transport"
            )
        return result

    def clear_display(self):
        self.driver.clear()

    def clear(self):
        """Alias for clear_display"""
        return self.clear_display()

    def display_image(self, image):
        self.driver.display_image(image)

    def display(self, image):
        """Alias for display_image"""
        return self.display_image(image)

    def display_bytes(self, image_bytes):
        self.driver.display_bytes(image_bytes)
