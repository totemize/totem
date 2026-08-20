"""Waveshare 2.13-inch e-Paper HAT V4 driver."""

import time

from PIL import Image

from totem.devices.display.drivers._waveshare_2in13_base import (
    Waveshare2in13Base,
)
from totem.logging import logger


class Driver(Waveshare2in13Base):
    """Controller protocol for Waveshare's V4 monochrome panel."""

    RESET_HIGH_SECONDS = 0.02
    RESET_LOW_SECONDS = 0.002
    SLEEP_VALUE = 0x01
    TEMPERATURE_SENSOR_CONTROL = 0x18
    WRITE_RAM_PREVIOUS = 0x26
    FULL_UPDATE_CONTROL = 0xF7
    PARTIAL_UPDATE_CONTROL = 0xFF
    PARTIAL_BORDER_WAVEFORM = 0x80
    FULL_BORDER_WAVEFORM = 0x05
    PARTIAL_RESET_SECONDS = 0.001
    BUSY_ASSERT_TIMEOUT_SECONDS = 1.0
    REFRESH_FALLBACK_SECONDS = 30.0

    def __init__(self):
        super().__init__()
        self._previous_frame = None
        self._partial_mode_active = False

    @property
    def partial_refresh_ready(self) -> bool:
        return self.initialized and self._previous_frame is not None

    def init(self):
        logger.info("Initializing Waveshare 2.13in e-Paper HAT V4")
        self._previous_frame = None
        self._partial_mode_active = False
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
        self.send_data(self.FULL_BORDER_WAVEFORM)
        self.send_command(self.DISPLAY_UPDATE_CONTROL_1)
        self.send_data(0x00)
        self.send_data(0x80)
        self.send_command(self.TEMPERATURE_SENSOR_CONTROL)
        self.send_data(0x80)
        self.wait_until_idle()

        self.initialized = True
        logger.info("Waveshare 2.13in V4 initialization complete")
        return True

    def _activate_update(self, control: int):
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(control)
        self.send_command(self.MASTER_ACTIVATION)
        self.last_refresh_confirmed_by_busy = self.wait_for_refresh(
            busy_assert_timeout=self.BUSY_ASSERT_TIMEOUT_SECONDS,
            fallback_timeout=self.REFRESH_FALLBACK_SECONDS,
        )

    def _update(self):
        self._activate_update(self.FULL_UPDATE_CONTROL)

    def _update_partial(self):
        self._activate_update(self.PARTIAL_UPDATE_CONTROL)

    def _configure_partial_refresh(self):
        # Waveshare's V4 reference pulses reset before every partial frame.
        # This long-lived driver needs that transition only once per burst.
        if not self._partial_mode_active:
            self.GPIO.output(self.reset_pin, self.GPIO.LOW)
            time.sleep(self.PARTIAL_RESET_SECONDS)
            self.GPIO.output(self.reset_pin, self.GPIO.HIGH)

        self.send_command(self.BORDER_WAVEFORM_CONTROL)
        self.send_data(self.PARTIAL_BORDER_WAVEFORM)
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data((self.NATIVE_HEIGHT - 1) & 0xFF)
        self.send_data(((self.NATIVE_HEIGHT - 1) >> 8) & 0xFF)
        self.send_data(0x00)
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x03)
        self._prepare_frame_write()

    def display_bytes(self, image_bytes):
        """Full refresh and seed both RAM planes for later partial updates."""
        payload = self._frame_payload(image_bytes)
        if not self.initialized:
            self.init()

        # Any failure after the first controller mutation makes its two RAM
        # planes unknowable. Invalidate first so early command/data failures
        # cannot leave a stale partial-refresh baseline behind.
        self._previous_frame = None
        self._partial_mode_active = False
        try:
            self.send_command(self.BORDER_WAVEFORM_CONTROL)
            self.send_data(self.FULL_BORDER_WAVEFORM)
            self._prepare_frame_write()
            self._write_frame(self.WRITE_RAM, payload)
            self._write_frame(self.WRITE_RAM_PREVIOUS, payload)
            self._update()
        except Exception:
            self._previous_frame = None
            self._partial_mode_active = False
            raise
        self._previous_frame = payload
        self._partial_mode_active = False

    def display_image_partial(self, image):
        if not isinstance(image, Image.Image):
            raise TypeError("display_image_partial requires a PIL Image")
        self.display_bytes_partial(self._image_buffer(image))
        return True

    def display_bytes_partial(self, image_bytes):
        """Differential full-frame refresh without reinitializing each frame."""
        payload = self._frame_payload(image_bytes)
        if not self.partial_refresh_ready:
            # A retained panel does not imply valid controller RAM after boot.
            # Establish the two-plane baseline with one safe full refresh.
            self.display_bytes(payload)
            return

        previous = self._previous_frame
        try:
            self._configure_partial_refresh()
            self._write_frame(self.WRITE_RAM_PREVIOUS, previous)
            self._write_frame(self.WRITE_RAM, payload)
            self._update_partial()
        except Exception:
            self._previous_frame = None
            self._partial_mode_active = False
            raise
        self._previous_frame = payload
        self._partial_mode_active = True

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
