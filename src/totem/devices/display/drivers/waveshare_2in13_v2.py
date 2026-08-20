"""Waveshare 2.13-inch e-Paper HAT V2/Rev 2.1 driver."""

import time

from PIL import Image

from totem.devices.display.drivers._waveshare_2in13_base import (
    Waveshare2in13Base,
)
from totem.logging import logger


class Driver(Waveshare2in13Base):
    """Controller protocol for Waveshare V2 panels and Rev 2.1 HATs."""

    SLEEP_VALUE = 0x03
    REFRESH_SETTLE_SECONDS = 4.0
    LUT_FULL_UPDATE = (
        0x80, 0x60, 0x40, 0x00, 0x00, 0x00, 0x00,
        0x10, 0x60, 0x20, 0x00, 0x00, 0x00, 0x00,
        0x80, 0x60, 0x40, 0x00, 0x00, 0x00, 0x00,
        0x10, 0x60, 0x20, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x03, 0x03, 0x00, 0x00, 0x02,
        0x09, 0x09, 0x00, 0x00, 0x02,
        0x03, 0x03, 0x00, 0x00, 0x02,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x15, 0x41, 0xA8, 0x32, 0x30, 0x0A,
    )

    def init(self):
        logger.info("Initializing Waveshare 2.13in e-Paper HAT V2/Rev 2.1")
        self._initialize_transport()
        self.reset()
        self.wait_until_idle()
        self.send_command(self.SW_RESET)
        self.wait_until_idle()

        self.send_command(0x74)  # Analog block control.
        self.send_data(0x54)
        self.send_command(0x7E)  # Digital block control.
        self.send_data(0x3B)
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x01)
        self._prepare_frame_write()

        self.send_command(self.BORDER_WAVEFORM_CONTROL)
        self.send_data(0x03)
        self.send_command(0x2C)  # VCOM voltage.
        self.send_data(0x55)
        self.send_command(0x03)
        self.send_data(self.LUT_FULL_UPDATE[70])
        self.send_command(0x04)
        self.send_data(self.LUT_FULL_UPDATE[71:74])
        self.send_command(0x3A)
        self.send_data(self.LUT_FULL_UPDATE[74])
        self.send_command(0x3B)
        self.send_data(self.LUT_FULL_UPDATE[75])
        self.send_command(0x32)
        self.send_data(self.LUT_FULL_UPDATE[:70])
        self.wait_until_idle()

        self.initialized = True
        logger.info("Waveshare 2.13in V2 initialization complete")
        return True

    def _prepare_frame_write(self):
        # V2 full-update mode writes native Y from 249 down to zero.
        self.send_command(self.SET_RAM_X_ADDRESS_START_END_POSITION)
        self.send_data(0x00)
        self.send_data(0x0F)
        self.send_command(self.SET_RAM_Y_ADDRESS_START_END_POSITION)
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_command(self.SET_RAM_X_ADDRESS_COUNTER)
        self.send_data(0x00)
        self.send_command(self.SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(0xF9)
        self.send_data(0x00)

    def _update(self):
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC7)
        self.send_command(self.MASTER_ACTIVATION)
        # Match Waveshare's V2 protocol and Pwnagotchi's proven Rev 2.1 path:
        # BUSY is used to wait for completion when asserted, but observing the
        # leading edge is not required. Rev 2.1 HATs exist that refresh
        # correctly while GPIO24 never exposes that edge to the host.
        self.wait_until_idle()
        # Pwnagotchi keeps the controller powered after this call. Totem may
        # sleep it immediately, so retain power long enough for a full update
        # even when the HAT exposes no usable BUSY signal.
        time.sleep(self.REFRESH_SETTLE_SECONDS)

    def _image_buffer(self, image: Image.Image) -> bytearray:
        image = image.convert("1")
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))

        pixels = image.load()
        payload = bytearray([0xFF] * self.FRAME_BYTES)
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if pixels[x, y] == 0:
                    payload[(y // 8) + x * self.LINE_BYTES] &= ~(
                        0x80 >> (y % 8)
                    )
        return payload
