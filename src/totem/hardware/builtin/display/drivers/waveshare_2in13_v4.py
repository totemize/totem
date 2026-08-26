"""Waveshare 2.13-inch V4 controller for the built-in display provider."""

from PIL import Image

from ._waveshare_2in13_base import Waveshare2in13Base


class Driver(Waveshare2in13Base):
    """Controller protocol for Waveshare's V4 monochrome panel."""

    TRANSPORT_KIND = "spi-gpio"
    RESET_HIGH_SECONDS = 0.02
    RESET_LOW_SECONDS = 0.002
    SLEEP_VALUE = 0x01
    TEMPERATURE_SENSOR_CONTROL = 0x18
    BUSY_ASSERT_TIMEOUT_SECONDS = 1.0
    REFRESH_FALLBACK_SECONDS = 30.0

    def init(self) -> bool:
        self._initialize_transport()
        self.reset()
        self.wait_until_idle()
        self.send_command(self.SW_RESET)
        self.wait_until_idle()
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data((self.NATIVE_HEIGHT - 1) & 0xFF)
        self.send_data(((self.NATIVE_HEIGHT - 1) >> 8) & 0xFF)
        self.send_data(0x00)
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x03)
        self._prepare_frame_write()
        self.send_command(self.BORDER_WAVEFORM_CONTROL)
        self.send_data(0x05)
        self.send_command(self.DISPLAY_UPDATE_CONTROL_1)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(self.TEMPERATURE_SENSOR_CONTROL)
        self.send_data(0x80)
        self.wait_until_idle()
        self.initialized = True
        return True

    def _update(self) -> None:
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xF7)
        self.send_command(self.MASTER_ACTIVATION)
        self.last_refresh_confirmed_by_busy = self.wait_for_refresh(
            busy_assert_timeout=self.BUSY_ASSERT_TIMEOUT_SECONDS,
            fallback_timeout=self.REFRESH_FALLBACK_SECONDS,
        )

    def _image_buffer(self, image: Image.Image) -> bytearray:
        image = image.convert("1")
        if image.size == (self.WIDTH, self.HEIGHT):
            image = image.rotate(90, expand=True)
        elif image.size != (self.NATIVE_WIDTH, self.NATIVE_HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT)).rotate(90, expand=True)
        payload = bytearray(image.tobytes("raw"))
        if len(payload) != self.FRAME_BYTES:
            raise ValueError("Unexpected framebuffer size: {} != {}".format(len(payload), self.FRAME_BYTES))
        return payload
