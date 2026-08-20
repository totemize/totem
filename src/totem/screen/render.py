"""Render screen state into monochrome display-sized frames."""

import os
from pathlib import Path
from typing import Iterable, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from totem.screen.model import ScreenFrame, ScreenState

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
FONT_BOLD_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


class FrameRenderer:
    """Turn semantic frames into 1-bit PIL images."""

    def __init__(
        self,
        width: int = 250,
        height: int = 122,
        *,
        font_path: Optional[str] = None,
        bold_font_path: Optional[str] = None,
        rotation: int = 0,
    ):
        if rotation not in (0, 180):
            raise ValueError("Screen rotation must be 0 or 180 degrees")
        self.width = width
        self.height = height
        self.rotation = rotation
        self.font_path = self._font_path(
            font_path or os.environ.get("TOTEM_SCREEN_FONT"),
            FONT_CANDIDATES,
        )
        self.bold_font_path = self._font_path(
            bold_font_path or os.environ.get("TOTEM_SCREEN_BOLD_FONT"),
            FONT_BOLD_CANDIDATES,
        )

    @staticmethod
    def _font_path(
        requested: Optional[str], candidates: Iterable[str]
    ) -> Optional[str]:
        if requested:
            path = Path(requested)
            if not path.is_file():
                raise FileNotFoundError("Screen font not found: {}".format(path))
            return str(path)
        return next((path for path in candidates if Path(path).is_file()), None)

    def _font(self, size: int, *, bold: bool = False):
        path = self.bold_font_path if bold else self.font_path
        if path is not None:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    @staticmethod
    def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top

    def _centered_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font,
        *,
        y_center: Optional[float] = None,
    ) -> None:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_width = right - left
        text_height = bottom - top
        center = self.height / 2 if y_center is None else y_center
        x = (self.width - text_width) / 2 - left
        y = center - text_height / 2 - top
        draw.text((round(x), round(y)), text, font=font, fill=0)

    def _fit_font(self, draw: ImageDraw.ImageDraw, text: str, maximum: int):
        for size in range(maximum, 7, -1):
            font = self._font(size, bold=True)
            width, height = self._text_size(draw, text, font)
            if width <= self.width - 16 and height <= self.height - 16:
                return font
        return self._font(8, bold=True)

    def render(self, frame: ScreenFrame) -> Image.Image:
        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        if frame.state == ScreenState.BOOTING and frame.services:
            self._render_services(draw, frame)
        elif frame.state == ScreenState.BOOTING:
            font = self._fit_font(draw, frame.headline or "TOTEM", 64)
            self._centered_text(draw, frame.headline or "TOTEM", font)
        elif frame.state == ScreenState.IDLE:
            font = self._fit_font(draw, frame.headline or "(^_^)", 48)
            self._centered_text(draw, frame.headline or "(^_^)", font)
        else:
            font = self._fit_font(draw, frame.headline, 32)
            self._centered_text(draw, frame.headline, font)

        return image.rotate(self.rotation)

    def _render_services(self, draw: ImageDraw.ImageDraw, frame: ScreenFrame) -> None:
        title_font = self._font(16, bold=True)
        service_font = self._font(17)
        title = frame.headline or "STARTING"
        title_height = self._text_size(draw, title, title_font)[1]
        row_height = max(20, self._text_size(draw, "Ag", service_font)[1] + 4)
        block_height = title_height + 5 + row_height * len(frame.services)
        y = max(1, (self.height - block_height) // 2)

        self._centered_text(
            draw,
            title,
            title_font,
            y_center=y + title_height / 2,
        )
        y += title_height + 5
        for service in frame.services:
            marker_top = y + max(2, row_height // 2 - 7)
            if service.ready:
                draw.line(
                    ((20, marker_top + 7), (25, marker_top + 12)),
                    fill=0,
                    width=2,
                )
                draw.line(
                    ((25, marker_top + 12), (34, marker_top)),
                    fill=0,
                    width=2,
                )
            else:
                draw.ellipse(
                    (21, marker_top + 1, 33, marker_top + 13),
                    outline=0,
                    width=1,
                )
            draw.text((42, y), service.label, font=service_font, fill=0)
            y += row_height
