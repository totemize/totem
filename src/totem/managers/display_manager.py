"""Legacy display name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient


class DisplayManager:
    """Compatibility-only display facade; it never owns a display driver."""

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

    @property
    def width(self) -> int:
        return int(self.client.display_dimensions()["width"])

    @property
    def height(self) -> int:
        return int(self.client.display_dimensions()["height"])

    def clear_screen(self) -> None:
        self.client.clear_screen()

    def display_text(
        self,
        text: str,
        font_size: int = 24,
        x: int = 10,
        y: int = 10,
        font_name: Optional[str] = None,
    ) -> None:
        self.client.display_text(text, font_size, x, y, font_name)

    def display_image_from_file(self, file_path: str) -> None:
        self.client.display_image_from_file(file_path)

    def display_image(self, image: object) -> None:
        self.client.display_image(image)

    def display_bytes(self, image_bytes: bytes) -> None:
        self.client.display_bytes(image_bytes)

    def display_encoded_image(self, image_bytes: bytes) -> None:
        self.client.display_encoded_image(image_bytes)

    def sleep(self) -> None:
        self.client.display_sleep()

    def wake(self) -> None:
        self.client.display_wake()

    def close(self) -> None:
        """Close this facade only; the injected client/runtime remains shared."""

        self._closed = True
