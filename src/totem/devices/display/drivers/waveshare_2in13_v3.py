"""Waveshare 2.13-inch e-Paper HAT V3 driver."""

from PIL import Image

from totem.devices.display.drivers._waveshare_2in13_base import (
    Waveshare2in13Base,
)
from totem.logging import logger


class Driver(Waveshare2in13Base):
    """Controller protocol for Waveshare's V3 monochrome panel."""

    RESET_HIGH_SECONDS = 0.02
    RESET_LOW_SECONDS = 0.002
    SLEEP_VALUE = 0x01
    LUT_FULL_UPDATE = (
        128, 74, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        64, 74, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        128, 74, 64, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        64, 74, 128, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        15, 0, 0, 0, 0, 0, 0,
        15, 0, 0, 15, 0, 0, 2,
        15, 0, 0, 0, 0, 0, 0,
        1, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        0, 0, 0, 0, 0, 0, 0,
        34, 34, 34, 34, 34, 34, 0, 0, 0,
        34, 23, 65, 0, 50, 54,
    )

    def init(self):
        logger.info("Initializing Waveshare 2.13in e-Paper HAT V3")
        self._initialize_transport()
        self.reset()
        self.wait_until_idle()
        self.send_command(self.SW_RESET)
        self.wait_until_idle()

        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x03)
        self._prepare_frame_write()
        self.send_command(self.BORDER_WAVEFORM_CONTROL)
        self.send_data(0x05)
        self.send_command(self.DISPLAY_UPDATE_CONTROL_1)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(0x18)
        self.send_data(0x80)
        self.wait_until_idle()
        self._set_lut(self.LUT_FULL_UPDATE)

        self.initialized = True
        logger.info("Waveshare 2.13in V3 initialization complete")
        return True

    def _set_lut(self, lut):
        if len(lut) != 159:
            raise ValueError("V3 full-update LUT must contain 159 bytes")
        self.send_command(0x32)
        self.send_data(lut[:153])
        self.wait_until_idle()
        self.send_command(0x3F)
        self.send_data(lut[153])
        self.send_command(0x03)
        self.send_data(lut[154])
        self.send_command(0x04)
        self.send_data(lut[155:158])
        self.send_command(0x2C)
        self.send_data(lut[158])

    def _update(self):
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC7)
        self.send_command(self.MASTER_ACTIVATION)
        self.wait_until_idle(require_busy=True)

    def _image_buffer(self, image: Image.Image) -> bytearray:
        image = image.convert("1")
        if image.size == (self.WIDTH, self.HEIGHT):
            image = image.rotate(90, expand=True)
        elif image.size != (self.NATIVE_WIDTH, self.NATIVE_HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT)).rotate(90, expand=True)
        payload = bytearray(image.tobytes("raw"))
        if len(payload) != self.FRAME_BYTES:
            raise ValueError(
                f"Unexpected framebuffer size: {len(payload)} != {self.FRAME_BYTES}"
            )
        return payload
