"""High-level access to the Totem UPS."""

import os
from typing import Optional

from totem.devices.ups.ups import UPS, UPSStatus
from totem.logging import logger


class UPSManager:
    """Initialize one UPS driver and expose read-only telemetry."""

    def __init__(self, driver_name: Optional[str] = None):
        environment_driver = os.environ.get("TOTEM_UPS_DRIVER", "").strip()
        self.driver_name = driver_name or environment_driver or None
        self.ups_device = UPS(self.driver_name)
        self.ups_device.initialize()
        logger.info(
            "Initialized UPS driver %s",
            type(self.ups_device.driver).__module__,
        )

    def get_status(self) -> UPSStatus:
        return self.ups_device.get_status()

    def close(self) -> None:
        self.ups_device.close()
