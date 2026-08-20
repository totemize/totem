"""High-level, serialized access to an E-Ink display."""

import io
import os
from pathlib import Path
import threading
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from totem.devices.display.display import (
    EInk,
    FULL_REFRESH,
    PARTIAL_REFRESH,
    normalize_refresh_mode,
)
from totem.logging import logger


class DisplayManager:
    """Render text and images through one selected display driver."""

    DEFAULT_FULL_REFRESH_EVERY = 20
    FULL_REFRESH_EVERY_ENV = "TOTEM_EINK_FULL_REFRESH_EVERY"

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        full_refresh_every: Optional[int] = None,
    ):
        self._lock = threading.RLock()
        self._partial_refreshes = 0
        self._partial_fallback_warned = False
        self.full_refresh_every = self._resolve_full_refresh_every(full_refresh_every)
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

    @classmethod
    def _resolve_full_refresh_every(cls, configured: Optional[int]) -> int:
        value = configured
        if value is None:
            value = os.environ.get(cls.FULL_REFRESH_EVERY_ENV, "").strip()
        if value == "" or value is None:
            return cls.DEFAULT_FULL_REFRESH_EVERY
        if isinstance(value, bool):
            raise ValueError("full_refresh_every must be a positive integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("full_refresh_every must be a positive integer") from exc
        if parsed <= 0:
            raise ValueError("full_refresh_every must be a positive integer")
        return parsed

    def _effective_refresh_mode(self, requested, *, raw: bool = False) -> str:
        mode = normalize_refresh_mode(requested)
        if mode == FULL_REFRESH:
            return mode
        if not self.eink_device.supports_refresh_mode(mode, raw=raw):
            if not self._partial_fallback_warned:
                logger.warning(
                    "Display driver %s has no partial refresh; using full refresh",
                    type(self.eink_device.driver).__module__,
                )
                self._partial_fallback_warned = True
            return FULL_REFRESH
        if not self.eink_device.partial_refresh_ready():
            logger.debug("Using a full refresh to establish the partial baseline")
            return FULL_REFRESH
        if self._partial_refreshes + 1 >= self.full_refresh_every:
            logger.info(
                "Promoting partial refresh %s to full refresh for panel hygiene",
                self.full_refresh_every,
            )
            return FULL_REFRESH
        return PARTIAL_REFRESH

    def _record_refresh(self, effective_mode: str) -> None:
        if effective_mode == PARTIAL_REFRESH:
            self._partial_refreshes += 1
        else:
            self._partial_refreshes = 0

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
            self._record_refresh(FULL_REFRESH)

    def display_text(
        self,
        text: str,
        font_size: int = 24,
        x: int = 10,
        y: int = 10,
        font_name: Optional[str] = None,
        refresh_mode=FULL_REFRESH,
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
        self.display_image(image, refresh_mode=refresh_mode)

    def display_image_from_file(
        self, file_path: str, refresh_mode=FULL_REFRESH
    ) -> None:
        path = Path(file_path)
        with Image.open(path) as source:
            image = source.copy()
        self.display_image(image, refresh_mode=refresh_mode)

    def display_image(self, image: Image.Image, refresh_mode=FULL_REFRESH) -> None:
        if not isinstance(image, Image.Image):
            raise TypeError("display_image requires a PIL Image")
        with self._lock:
            effective_mode = self._effective_refresh_mode(refresh_mode)
            self.eink_device.display_image(image, refresh_mode=effective_mode)
            self._record_refresh(effective_mode)

    def display_bytes(self, image_bytes: bytes, refresh_mode=FULL_REFRESH) -> None:
        if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("display_bytes requires bytes-like data")
        with self._lock:
            effective_mode = self._effective_refresh_mode(refresh_mode, raw=True)
            self.eink_device.display_bytes(
                bytes(image_bytes), refresh_mode=effective_mode
            )
            self._record_refresh(effective_mode)

    def display_encoded_image(
        self, image_bytes: bytes, refresh_mode=FULL_REFRESH
    ) -> None:
        """Decode PNG/JPEG bytes and render the resulting image."""
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.copy()
        self.display_image(image, refresh_mode=refresh_mode)

    def sleep(self) -> None:
        with self._lock:
            sleep = getattr(self.eink_device.driver, "sleep", None)
            if sleep is None:
                raise NotImplementedError("Display driver does not support sleep")
            sleep()

    def wake(self) -> None:
        with self._lock:
            self.eink_device.initialize()
            self._record_refresh(FULL_REFRESH)

    def close(self) -> None:
        with self._lock:
            self.eink_device.driver.close()
