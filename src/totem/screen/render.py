"""Render screen state into monochrome display-sized frames."""

import math
import os
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from totem.screen.model import (
    RuntimeFrame,
    RuntimeScene,
    RuntimeSnapshot,
    ScreenFrame,
    ScreenState,
)

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)
FONT_BOLD_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)

FALLBACK_PERSISTENT_TEXT_STROKE = 1
PERSISTENT_ICON_STROKE = 1
CAPTION_FONT_SIZE = 9
CAPTION_MIN_FONT_SIZE = 8
CAPTION_SIDE_MARGIN = 8
CAPTION_FOOTER_GAP = 3
CAPTION_BAND_HEIGHT = 12


class VectorKaomoji:
    """A tiny vector glyph set for the exact runtime expression catalog.

    The target image has DejaVu but not a CJK font, so relying on text shaping
    would turn ``ﾉ``/``ヮ`` and several symbols into tofu.  This deliberately
    closed vector alphabet is resolution-independent and fails loudly if new
    presentation copy is added without artwork.
    """

    WIDTHS: Dict[str, int] = {
        " ": 3,
        "(": 3,
        ")": 3,
        "•": 4,
        "◐": 6,
        "◑": 6,
        "◒": 6,
        "◓": 6,
        "‿": 6,
        "ᴗ": 6,
        "ω": 7,
        "´": 3,
        "o": 5,
        "!": 3,
        "_": 5,
        "?": 5,
        "-": 5,
        ">": 5,
        "¬": 5,
        "⌐": 6,
        "■": 6,
        "˵": 4,
        "✧": 7,
        "★": 7,
        "\\": 5,
        "/": 5,
        "ﾉ": 5,
        "◕": 6,
        "ヮ": 7,
        "⇄": 9,
        "↔": 9,
        "→": 9,
        "←": 9,
        "✓": 6,
        "ڡ": 7,
        "⚡": 7,
        "－": 7,
        "=": 6,
        "z": 5,
        "×": 6,
        "⌁": 8,
    }

    @classmethod
    def supports(cls, text: str) -> bool:
        return all(character in cls.WIDTHS for character in text)

    @classmethod
    def draw(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        bounds: Tuple[int, int, int, int],
        *,
        left_aligned: bool = False,
        fixed_scale: Optional[int] = None,
    ) -> Tuple[int, int, int, int]:
        if not cls.supports(text):
            missing = sorted(set(text) - set(cls.WIDTHS))
            raise ValueError("Unsupported screen vector glyphs: {!r}".format(missing))

        left, top, right, bottom = bounds
        units = sum(cls.WIDTHS[character] for character in text)
        units += max(0, len(text) - 1)
        maximum_scale = max(
            1, min(5, int(min((right - left) / units, (bottom - top) / 10)))
        )
        scale = maximum_scale if fixed_scale is None else fixed_scale
        if scale < 1 or scale > maximum_scale:
            raise ValueError("Vector glyph scale does not fit the requested bounds")
        ink_width = units * scale
        ink_height = 9 * scale
        x = left if left_aligned else left + (right - left - ink_width) // 2
        y = top + (bottom - top - ink_height) // 2
        origin = (x, y)
        for character in text:
            width = cls.WIDTHS[character]
            cls._glyph(draw, character, x, y, width, scale)
            x += (width + 1) * scale
        return (origin[0], origin[1], origin[0] + ink_width, origin[1] + ink_height)

    @staticmethod
    def _star(draw, x: int, y: int, width: int, scale: int) -> None:
        center_x = x + width * scale / 2
        center_y = y + 4.5 * scale
        points = []
        for index in range(10):
            radius = (3.5 if index % 2 == 0 else 1.5) * scale
            angle = -math.pi / 2 + index * math.pi / 5
            points.append(
                (
                    round(center_x + math.cos(angle) * radius),
                    round(center_y + math.sin(angle) * radius),
                )
            )
        draw.polygon(points, fill=0)

    @classmethod
    def _glyph(
        cls,
        draw: ImageDraw.ImageDraw,
        character: str,
        x: int,
        y: int,
        width: int,
        scale: int,
    ) -> None:
        if character == " ":
            return
        stroke = max(1, scale // 2)
        right = x + width * scale
        bottom = y + 9 * scale
        mid_x = x + width * scale // 2
        mid_y = y + 9 * scale // 2

        def line(points, size=stroke):
            draw.line(points, fill=0, width=size)

        if character == "(":
            draw.arc((x, y, right + 2 * scale, bottom), 90, 270, fill=0, width=stroke)
        elif character == ")":
            draw.arc((x - 2 * scale, y, right, bottom), 270, 90, fill=0, width=stroke)
        elif character == "•":
            radius = max(2, scale)
            draw.ellipse(
                (mid_x - radius, mid_y - radius, mid_x + radius, mid_y + radius),
                fill=0,
            )
        elif character in ("◐", "◑", "◒", "◓"):
            eye = (x, y + scale, right, bottom - scale)
            angles = {
                "◐": (90, 270),
                "◑": (270, 450),
                "◒": (0, 180),
                "◓": (180, 360),
            }
            draw.pieslice(eye, *angles[character], fill=0)
            draw.ellipse(eye, outline=0, width=stroke)
        elif character == "‿":
            draw.arc(
                (x, y + scale, right, bottom - scale),
                0,
                180,
                fill=0,
                width=stroke,
            )
        elif character == "ᴗ":
            line(
                (
                    (x + scale, y + 4 * scale),
                    (mid_x, y + 7 * scale),
                    (right - scale, y + 4 * scale),
                )
            )
        elif character == "ω":
            draw.arc(
                (x, y + 2 * scale, mid_x + scale, bottom - scale),
                0,
                180,
                fill=0,
                width=stroke,
            )
            draw.arc(
                (mid_x - scale, y + 2 * scale, right, bottom - scale),
                0,
                180,
                fill=0,
                width=stroke,
            )
        elif character == "´":
            line(((x + scale, y + 3 * scale), (right - scale, y + scale)))
        elif character == "o":
            draw.ellipse(
                (x + scale, y + 2 * scale, right - scale, bottom - 2 * scale),
                outline=0,
                width=stroke,
            )
        elif character == "!":
            line(((mid_x, y + scale), (mid_x, y + 6 * scale)))
            draw.ellipse(
                (mid_x - stroke, bottom - 2 * scale, mid_x + stroke, bottom),
                fill=0,
            )
        elif character == "_" or character == "－":
            line(((x, y + 6 * scale), (right, y + 6 * scale)))
        elif character == "-":
            line(((x, mid_y), (right, mid_y)))
        elif character == ">":
            line(
                (
                    (x + scale, y + 2 * scale),
                    (right - scale, mid_y),
                    (x + scale, bottom - 2 * scale),
                )
            )
        elif character == "?":
            line(
                (
                    (x + scale, y + 2 * scale),
                    (mid_x, y + scale),
                    (right - scale, y + 2 * scale),
                    (right - scale, y + 4 * scale),
                    (mid_x, y + 5 * scale),
                    (mid_x, y + 6 * scale),
                )
            )
            draw.ellipse(
                (mid_x - stroke, bottom - 2 * scale, mid_x + stroke, bottom),
                fill=0,
            )
        elif character == "¬":
            line(((x, y + 3 * scale), (right, y + 3 * scale)))
            line(((right, y + 3 * scale), (right, y + 6 * scale)))
        elif character == "⌐":
            line(((x + scale, y + 3 * scale), (right, y + 3 * scale)))
            line(((x + scale, y + 3 * scale), (x + scale, y + 7 * scale)))
        elif character == "■":
            draw.rectangle(
                (x + scale, y + 2 * scale, right - scale, bottom - 2 * scale),
                fill=0,
            )
        elif character == "˵":
            line(
                (
                    (x, y + 6 * scale),
                    (x + scale, y + 7 * scale),
                )
            )
            line(
                (
                    (x + 2 * scale, y + 5 * scale),
                    (x + 3 * scale, y + 6 * scale),
                )
            )
        elif character == "✧":
            line(
                (
                    (mid_x, y),
                    (right, mid_y),
                    (mid_x, bottom),
                    (x, mid_y),
                    (mid_x, y),
                )
            )
            line(((mid_x, y + 2 * scale), (mid_x, bottom - 2 * scale)))
            line(((x + 2 * scale, mid_y), (right - 2 * scale, mid_y)))
        elif character == "★":
            cls._star(draw, x, y, width, scale)
        elif character == "\\" or character == "ﾉ":
            line(((x + scale, y + scale), (right - scale, bottom - scale)))
        elif character == "/":
            line(((x + scale, bottom - scale), (right - scale, y + scale)))
        elif character == "◕":
            draw.ellipse((x, y + scale, right, bottom - scale), outline=0, width=stroke)
            radius = max(1, scale)
            draw.ellipse(
                (
                    mid_x,
                    y + 2 * scale,
                    mid_x + 2 * radius,
                    y + 2 * scale + 2 * radius,
                ),
                fill=0,
            )
        elif character == "ヮ":
            line(((x + scale, y + 3 * scale), (right - scale, y + 3 * scale)))
            line(
                (
                    (x + 2 * scale, y + 3 * scale),
                    (mid_x, y + 7 * scale),
                    (right - scale, y + 4 * scale),
                )
            )
        elif character in ("⇄", "↔"):
            if character == "⇄":
                upper = y + 3 * scale
                lower = y + 6 * scale
                line(((x + scale, upper), (right - scale, upper)))
                line(
                    (
                        (right - 3 * scale, upper - 2 * scale),
                        (right - scale, upper),
                        (right - 3 * scale, upper + 2 * scale),
                    )
                )
                line(
                    (
                        (x + scale, lower),
                        (right - scale, lower),
                    )
                )
                line(
                    (
                        (x + 3 * scale, lower - 2 * scale),
                        (x + scale, lower),
                        (x + 3 * scale, lower + 2 * scale),
                    )
                )
            else:
                middle = y + 5 * scale
                line(((x + scale, middle), (right - scale, middle)))
                line(
                    (
                        (x + 3 * scale, middle - 2 * scale),
                        (x + scale, middle),
                        (x + 3 * scale, middle + 2 * scale),
                    )
                )
                line(
                    (
                        (right - 3 * scale, middle - 2 * scale),
                        (right - scale, middle),
                        (right - 3 * scale, middle + 2 * scale),
                    )
                )
        elif character in ("→", "←"):
            middle = y + 5 * scale
            line(((x + scale, middle), (right - scale, middle)))
            if character == "→":
                line(
                    (
                        (right - 3 * scale, middle - 2 * scale),
                        (right - scale, middle),
                        (right - 3 * scale, middle + 2 * scale),
                    )
                )
            else:
                line(
                    (
                        (x + 3 * scale, middle - 2 * scale),
                        (x + scale, middle),
                        (x + 3 * scale, middle + 2 * scale),
                    )
                )
        elif character == "✓":
            line(
                (
                    (x, mid_y),
                    (x + 2 * scale, bottom - 2 * scale),
                    (right, y + scale),
                ),
                max(stroke, 2),
            )
        elif character == "ڡ":
            draw.arc(
                (x, y + scale, right, bottom - scale),
                0,
                180,
                fill=0,
                width=stroke,
            )
            line(((mid_x, y + 5 * scale), (mid_x, bottom - scale)))
            draw.ellipse((mid_x - stroke, y, mid_x + stroke, y + 2 * stroke), fill=0)
        elif character == "⚡":
            draw.polygon(
                (
                    (x + 4 * scale, y),
                    (x + scale, y + 5 * scale),
                    (x + 3 * scale, y + 5 * scale),
                    (x + 2 * scale, bottom),
                    (right - scale, y + 3 * scale),
                    (x + 4 * scale, y + 3 * scale),
                ),
                fill=0,
            )
        elif character == "=":
            line(((x, y + 3 * scale), (right, y + 3 * scale)))
            line(((x, y + 6 * scale), (right, y + 6 * scale)))
        elif character == "z":
            line(
                (
                    (x, y + 2 * scale),
                    (right, y + 2 * scale),
                    (x, y + 7 * scale),
                    (right, y + 7 * scale),
                )
            )
        elif character == "×":
            line(((x, y + scale), (right, bottom - scale)), max(stroke, 2))
            line(((right, y + scale), (x, bottom - scale)), max(stroke, 2))
        elif character == "⌁":
            line(
                (
                    (x, mid_y),
                    (x + 2 * scale, y + 3 * scale),
                    (x + 4 * scale, y + 6 * scale),
                    (right, mid_y),
                )
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
        path = (self.bold_font_path or self.font_path) if bold else self.font_path
        if path is not None:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    @staticmethod
    def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top

    @property
    def persistent_text_stroke(self) -> int:
        """Use synthetic weight only when no real bold face is installed."""

        return 0 if self.bold_font_path is not None else FALLBACK_PERSISTENT_TEXT_STROKE

    def _persistent_text_bbox(self, draw: ImageDraw.ImageDraw, text: str, font):
        return draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=self.persistent_text_stroke,
        )

    def _persistent_text_size(
        self, draw: ImageDraw.ImageDraw, text: str, font
    ) -> Tuple[int, int]:
        left, top, right, bottom = self._persistent_text_bbox(draw, text, font)
        return right - left, bottom - top

    def _draw_persistent_text(self, draw, position, text: str, font) -> None:
        draw.text(
            position,
            text,
            font=font,
            fill=0,
            stroke_width=self.persistent_text_stroke,
            stroke_fill=0,
        )

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

    @staticmethod
    def footer_counts(
        snapshot: RuntimeSnapshot,
    ) -> Tuple[int, int, int, Optional[int]]:
        """Global mesh / direct peers / friends / kind-1 notes."""

        return (
            snapshot.mesh_size,
            snapshot.peer_count,
            snapshot.recognized_count,
            snapshot.note_count,
        )

    @classmethod
    def footer_text(cls, snapshot: RuntimeSnapshot) -> str:
        """The literal count order used beside the four distinct icons."""

        return " / ".join(
            "?" if value is None else str(value)
            for value in cls.footer_counts(snapshot)
        )

    def render_runtime(self, frame: RuntimeFrame) -> Image.Image:
        """Render the persistent header/footer around one exact scene frame."""

        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        header_bottom = 20
        footer_top = self.height - 20
        draw.line(
            ((4, header_bottom), (self.width - 5, header_bottom)),
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )
        draw.line(
            ((4, footer_top), (self.width - 5, footer_top)),
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )
        self._render_header(draw, frame.snapshot, header_bottom)
        caption_bounds = self._caption_bounds(footer_top)
        content_bounds = (
            8,
            header_bottom + 3,
            self.width - 8,
            caption_bounds[1] - 2,
        )
        if frame.scene == RuntimeScene.NON_TOTEM_PEER:
            # The glasses are props, not a camera move.  Hold the face at one
            # left-side origin and one scale while the props extend rightward.
            VectorKaomoji.draw(
                draw,
                frame.expression,
                content_bounds,
                left_aligned=True,
                fixed_scale=3,
            )
        else:
            VectorKaomoji.draw(draw, frame.expression, content_bounds)
        self._render_caption(draw, frame, caption_bounds)
        self._render_footer(draw, frame.snapshot, footer_top)
        return image.rotate(self.rotation)

    def _caption_bounds(self, footer_top: int) -> Tuple[int, int, int, int]:
        bottom = footer_top - CAPTION_FOOTER_GAP
        return (
            CAPTION_SIDE_MARGIN,
            bottom - CAPTION_BAND_HEIGHT,
            self.width - CAPTION_SIDE_MARGIN,
            bottom,
        )

    @staticmethod
    def _font_glyph(font, character: str):
        try:
            mask = font.getmask(character)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ValueError(
                "Caption font cannot encode {!r}".format(character)
            ) from exc
        return mask.size, bytes(mask)

    @classmethod
    def _require_caption_glyphs(cls, font, caption: str) -> None:
        """Reject a font's missing-glyph box before it reaches e-ink."""

        missing = cls._font_glyph(font, "\U0010ffff")
        unsupported = sorted(
            {
                character
                for character in caption
                if not character.isspace()
                and cls._font_glyph(font, character) == missing
            }
        )
        if unsupported:
            raise ValueError("Unsupported caption glyphs: {!r}".format(unsupported))

    def _caption_layout(self, draw: ImageDraw.ImageDraw, caption: str, bounds):
        """Return one fixed baseline derived from the complete caption."""

        left, top, right, bottom = bounds
        for size in range(CAPTION_FONT_SIZE, CAPTION_MIN_FONT_SIZE - 1, -1):
            font = self._font(size, bold=True)
            self._require_caption_glyphs(font, caption)
            text_left, text_top, text_right, text_bottom = self._persistent_text_bbox(
                draw, caption, font
            )
            width = text_right - text_left
            height = text_bottom - text_top
            if width <= right - left and height <= bottom - top:
                x = left + (right - left - width) // 2 - text_left
                y = top + (bottom - top - height) // 2 - text_top
                return (
                    font,
                    x,
                    y,
                    (x + text_left, y + text_top, x + text_right, y + text_bottom),
                )
        raise ValueError("Caption does not fit the reserved band: {!r}".format(caption))

    def _render_caption(self, draw, frame: RuntimeFrame, bounds) -> None:
        if not frame.caption:
            if frame.caption_word_count:
                raise ValueError("Caption word count requires caption text")
            return
        words = frame.caption.split()
        if not 1 <= frame.caption_word_count <= len(words):
            raise ValueError("Caption word count is outside the selected caption")
        visible = " ".join(words[: frame.caption_word_count])
        font, x, y, _ = self._caption_layout(draw, frame.caption, bounds)
        self._draw_persistent_text(draw, (x, y), visible, font)

    def _render_header(
        self,
        draw: ImageDraw.ImageDraw,
        snapshot: RuntimeSnapshot,
        bottom: int,
    ) -> None:
        font = self._font(13, bold=True)
        battery_left = self.width - 31
        fips_left = battery_left - 24
        available = fips_left - 10
        original_name = snapshot.device_name.strip() or "TOTEM"
        name = original_name
        while (
            len(name) > 1
            and self._persistent_text_size(draw, name, font)[0] > available
        ):
            name = name[:-1]
        if name != original_name:
            while (
                len(name) > 1
                and self._persistent_text_size(draw, name + "…", font)[0] > available
            ):
                name = name[:-1]
            name += "…"
        _, text_top, _, text_bottom = self._persistent_text_bbox(draw, name, font)
        text_height = text_bottom - text_top
        text_y = (bottom - text_height) // 2 - text_top
        self._draw_persistent_text(draw, (5, text_y), name, font)
        self._fips_icon(draw, fips_left, 4, snapshot.fips_connected)
        self._battery_icon(draw, battery_left, 5, snapshot)

    @staticmethod
    def _fips_icon(draw: ImageDraw.ImageDraw, x: int, y: int, healthy: bool) -> None:
        nodes = ((x + 3, y + 10), (x + 9, y + 2), (x + 16, y + 10))
        draw.line(
            (nodes[0], nodes[1], nodes[2], nodes[0]),
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )
        for center_x, center_y in nodes:
            draw.ellipse(
                (center_x - 2, center_y - 2, center_x + 2, center_y + 2),
                fill=0,
            )
        if not healthy:
            draw.line(((x + 1, y + 1), (x + 18, y + 13)), fill=0, width=2)

    @staticmethod
    def _battery_icon(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        snapshot: RuntimeSnapshot,
    ) -> None:
        draw.rectangle(
            (x, y, x + 25, y + 11),
            outline=0,
            width=PERSISTENT_ICON_STROKE,
        )
        draw.rectangle((x + 26, y + 3, x + 28, y + 8), fill=0)
        percent = snapshot.power.battery_percent
        if snapshot.power.available and percent is not None:
            fill_width = round(21 * max(0.0, min(100.0, percent)) / 100)
            if fill_width:
                draw.rectangle((x + 2, y + 2, x + 1 + fill_width, y + 9), fill=0)
            if snapshot.power.power_plugged is True:
                # A white knockout with black vector ink stays legible over
                # both empty (white) and full (black) charge fills.
                draw.rectangle((x + 8, y + 1, x + 18, y + 10), fill=255)
                draw.polygon(
                    (
                        (x + 14, y + 1),
                        (x + 10, y + 6),
                        (x + 13, y + 6),
                        (x + 11, y + 10),
                        (x + 17, y + 4),
                        (x + 14, y + 4),
                    ),
                    fill=0,
                )
        else:
            draw.line(((x + 5, y + 3), (x + 9, y + 7), (x + 13, y + 3)), fill=0)
            draw.line(((x + 13, y + 3), (x + 17, y + 7), (x + 21, y + 3)), fill=0)

    def _render_footer(
        self,
        draw: ImageDraw.ImageDraw,
        snapshot: RuntimeSnapshot,
        top: int,
    ) -> None:
        font = self._font(11, bold=True)
        mesh_size, peer_count, recognized_count, note_count = self.footer_counts(
            snapshot
        )
        values = (mesh_size, peer_count, recognized_count)
        cursor = 6
        icon_y = top + 5
        _, text_top, _, text_bottom = self._persistent_text_bbox(draw, "0", font)
        text_y = top + (self.height - top - (text_bottom - text_top)) // 2 - text_top
        for index, value in enumerate(values):
            if index == 0:
                self._mesh_count_icon(draw, cursor, icon_y)
            elif index == 1:
                self._peer_count_icon(draw, cursor, icon_y)
            else:
                self._recognized_count_icon(draw, cursor, icon_y)
            cursor += 13
            label = str(value)
            self._draw_persistent_text(draw, (cursor, text_y), label, font)
            cursor += self._persistent_text_size(draw, label, font)[0] + 5
            if index < len(values) - 1:
                self._draw_persistent_text(draw, (cursor, text_y), "/", font)
                cursor += self._persistent_text_size(draw, "/", font)[0] + 5

        note_label = "?" if note_count is None else str(note_count)
        note_width = self._persistent_text_size(draw, note_label, font)[0]
        note_x = self.width - 6 - note_width - 14
        self._note_count_icon(draw, note_x, icon_y)
        self._draw_persistent_text(draw, (note_x + 14, text_y), note_label, font)

    @staticmethod
    def _mesh_count_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        points = ((x + 1, y + 7), (x + 5, y), (x + 10, y + 7))
        draw.line(
            (points[0], points[1], points[2], points[0]),
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )
        for px, py in points:
            draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=0)

    @staticmethod
    def _peer_count_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.ellipse(
            (x + 1, y, x + 5, y + 4),
            outline=0,
            width=PERSISTENT_ICON_STROKE,
        )
        draw.ellipse(
            (x + 6, y + 1, x + 10, y + 5),
            outline=0,
            width=PERSISTENT_ICON_STROKE,
        )
        draw.arc(
            (x, y + 3, x + 7, y + 10),
            180,
            360,
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )
        draw.arc(
            (x + 4, y + 4, x + 12, y + 11),
            180,
            360,
            fill=0,
            width=PERSISTENT_ICON_STROKE,
        )

    @staticmethod
    def _recognized_count_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        # A compact vector [•] friend mark.  Drawing it instead of relying on
        # a font keeps the exact symbol legible on the 1-bit display.
        draw.line(((x + 1, y), (x + 1, y + 9)), fill=0)
        draw.line(((x + 1, y), (x + 3, y)), fill=0)
        draw.line(((x + 1, y + 9), (x + 3, y + 9)), fill=0)
        draw.ellipse((x + 5, y + 3, x + 8, y + 6), fill=0)
        draw.line(((x + 12, y), (x + 12, y + 9)), fill=0)
        draw.line(((x + 10, y), (x + 12, y)), fill=0)
        draw.line(((x + 10, y + 9), (x + 12, y + 9)), fill=0)

    @staticmethod
    def _note_count_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        """Small paper-note glyph with a folded corner and two text rules."""

        draw.line(
            (
                (x + 1, y),
                (x + 8, y),
                (x + 11, y + 3),
                (x + 11, y + 10),
                (x + 1, y + 10),
                (x + 1, y),
            ),
            fill=0,
        )
        draw.line(((x + 8, y), (x + 8, y + 3), (x + 11, y + 3)), fill=0)
        draw.line(((x + 3, y + 5), (x + 8, y + 5)), fill=0)
        draw.line(((x + 3, y + 7), (x + 8, y + 7)), fill=0)

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
