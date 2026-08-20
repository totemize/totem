"""Waveshare 2.13-inch e-Paper HAT V1 driver."""

from PIL import Image

from totem.devices.display.drivers._waveshare_2in13_base import (
    Waveshare2in13Base,
)
from totem.logging import logger


class Driver(Waveshare2in13Base):
    """Controller protocol for the original Waveshare 2.13-inch panel."""

    SLEEP_VALUE = 0x01
    LUT_FULL_UPDATE = (
        0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
    )

    def init(self):
        logger.info("Initializing Waveshare 2.13in e-Paper HAT V1")
        self._initialize_transport()
        self.reset()
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(0x0C)
        self.send_data((0xD7, 0xD6, 0x9D))
        self.send_command(0x2C)
        self.send_data(0xA8)
        self.send_command(0x3A)
        self.send_data(0x1A)
        self.send_command(0x3B)
        self.send_data(0x08)
        self.send_command(self.BORDER_WAVEFORM_CONTROL)
        self.send_data(0x03)
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x03)
        self.send_command(0x32)
        self.send_data(self.LUT_FULL_UPDATE)
        self.initialized = True
        logger.info("Waveshare 2.13in V1 initialization complete")
        return True

    def _update(self):
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC4)
        self.send_command(self.MASTER_ACTIVATION)
        self.send_command(0xFF)
        self.wait_until_idle(require_busy=True)

    def _image_buffer(self, image: Image.Image) -> bytearray:
        image = image.convert("1")
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        pixels = image.load()
        payload = bytearray([0xFF] * self.FRAME_BYTES)
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if pixels[x, y] == 0:
                    native_y = self.NATIVE_HEIGHT - x - 1
                    payload[(y // 8) + native_y * self.LINE_BYTES] &= ~(
                        0x80 >> (y % 8)
                    )
        return payload

    def display_bytes(self, image_bytes):
        payload = bytes(image_bytes)
        if len(payload) != self.FRAME_BYTES:
            raise ValueError(
                f"Incorrect framebuffer size: expected {self.FRAME_BYTES} bytes, "
                f"got {len(payload)}"
            )
        if not self.initialized:
            self.init()

        self._set_window(0, 0, self.NATIVE_WIDTH, self.NATIVE_HEIGHT)
        for row in range(self.NATIVE_HEIGHT):
            self._set_cursor(0, row)
            self.send_command(self.WRITE_RAM)
            start = row * self.LINE_BYTES
            self.send_data(payload[start : start + self.LINE_BYTES])
        self._update()
