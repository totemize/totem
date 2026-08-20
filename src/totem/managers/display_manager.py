"""High-level, serialized access to an E-Ink display."""

import io
import os
from pathlib import Path
import threading
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from totem.devices.display.display import EInk
from totem.logging import logger


class DisplayManager:
    """Render text and images through one selected display driver."""

    def __init__(
        self, driver_name: Optional[str] = None, *, allow_mock: bool = False
    ):
        self._lock = threading.RLock()
        environment_driver = os.environ.get("TOTEM_EINK_DRIVER", "").strip()
        self.driver_name = driver_name or environment_driver or None
        self.eink_device = EInk(self.driver_name, allow_mock=allow_mock)
        self.eink_device.initialize()
        logger.info(
            "Initialized display driver %s with dimensions %sx%s",
            type(self.eink_device.driver).__module__,
            self.width,
            self.height,
        )

    @property
    def width(self) -> int:
        value = getattr(self.eink_device.driver, "width", None)
        if value is None:
            value = getattr(self.eink_device.driver, "WIDTH")
        return int(value)

    @property
    def height(self) -> int:
        value = getattr(self.eink_device.driver, "height", None)
        if value is None:
            value = getattr(self.eink_device.driver, "HEIGHT")
        return int(value)

    def clear_screen(self) -> None:
        with self._lock:
            self.eink_device.clear_display()

    def display_text(
        self,
        text: str,
        font_size: int = 24,
        x: int = 10,
        y: int = 10,
        font_name: Optional[str] = None,
    ) -> None:
        if font_size <= 0:
            raise ValueError("font_size must be positive")

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        try:
            font = (
                ImageFont.truetype(font_name, font_size)
                if font_name
                else ImageFont.load_default()
            )
        except (OSError, ValueError) as exc:
            logger.warning("Unable to load font %r: %s", font_name, exc)
            font = ImageFont.load_default()
        draw.text((x, y), text, font=font, fill=0)
        self.display_image(image)

    def display_image_from_file(self, file_path: str) -> None:
        path = Path(file_path)
        with Image.open(path) as source:
            image = source.copy()
        self.display_image(image)

    def display_image(self, image: Image.Image) -> None:
        if not isinstance(image, Image.Image):
            raise TypeError("display_image requires a PIL Image")
        with self._lock:
            self.eink_device.display_image(image)

    def display_bytes(self, image_bytes: bytes) -> None:
        if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("display_bytes requires bytes-like data")
        with self._lock:
            self.eink_device.display_bytes(bytes(image_bytes))

    def display_encoded_image(self, image_bytes: bytes) -> None:
        """Decode PNG/JPEG bytes and render the resulting image."""
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.copy()
        self.display_image(image)

    def sleep(self) -> None:
        with self._lock:
            sleep = getattr(self.eink_device.driver, "sleep", None)
            if sleep is None:
                raise NotImplementedError("Display driver does not support sleep")
            sleep()

    def wake(self) -> None:
        with self._lock:
            self.eink_device.initialize()

    def close(self) -> None:
        with self._lock:
            self.eink_device.driver.close()
