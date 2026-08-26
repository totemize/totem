"""Waveshare 2.13-inch V2 controller for the built-in display provider."""

from PIL import Image

from ._waveshare_2in13_base import Waveshare2in13Base


class Driver(Waveshare2in13Base):
    """Controller protocol for Waveshare V2 panels."""

    TRANSPORT_KIND = "spi-gpio"
    SLEEP_VALUE = 0x03
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

    def init(self) -> bool:
        self._initialize_transport()
        self.reset()
        self.wait_until_idle()
        self.send_command(self.SW_RESET)
        self.wait_until_idle()
        self.send_command(0x74)
        self.send_data(0x54)
        self.send_command(0x7E)
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
        self.send_command(0x2C)
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
        return True

    def _prepare_frame_write(self) -> None:
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

    def _update(self) -> None:
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC7)
        self.send_command(self.MASTER_ACTIVATION)
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
                    payload[(y // 8) + x * self.LINE_BYTES] &= ~(0x80 >> (y % 8))
        return payload
