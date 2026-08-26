"""Legacy E-Ink name translated through the canonical hardware client."""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient
from totem.devices.contracts import DeviceDriver


class EInkDeviceInterface(DeviceDriver):
    """Historical display-driver contract retained for import compatibility."""

    @abstractmethod
    def init(self):
        """Initialize the e-ink device."""
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        """Clear the e-ink display."""
        raise NotImplementedError

    @abstractmethod
    def display_image(self, image):
        """Display an image on the e-ink screen."""
        raise NotImplementedError

    @abstractmethod
    def display_bytes(self, image_bytes):
        """Display raw byte data on the e-ink screen."""
        raise NotImplementedError


class EInk:
    """Compatibility-only E-Ink facade; runtime ownership remains canonical."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name, "allow_mock": allow_mock}
        self._closed = False
        self._initialized = False

    def initialize(self, *args, **kwargs):
        """Record local compatibility readiness without starting a driver."""

        del args, kwargs
        self._initialized = True
        return True

    def clear_display(self):
        self.client.clear_screen()

    def clear(self):
        """Alias for :meth:`clear_display`."""

        return self.clear_display()

    def display_image(self, image):
        self.client.display_image(image)

    def display(self, image):
        """Alias for :meth:`display_image`."""

        return self.display_image(image)

    def display_bytes(self, image_bytes):
        self.client.display_bytes(image_bytes)

    def close(self) -> None:
        """Close this facade only; never stop the shared client or runtime."""

        self._closed = True
