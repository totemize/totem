#!/usr/bin/env python3
"""Shared transport and framebuffer contract for Waveshare 2.13-inch HATs.

Panel revisions use different controller initialization and pixel mappings;
those details live in versioned driver modules.
"""

from __future__ import annotations

from abc import abstractmethod
import time
from typing import Iterable

from PIL import Image

from totem.devices.display.display import EInkDeviceInterface
from totem.logging import logger


class MockSpiDev:
    """Minimal transport used only when hardware imports are unavailable."""

    def open(self, bus, device):
        logger.debug("Mock SPI opened on bus %s, device %s", bus, device)

    def xfer2(self, data):
        return [0] * len(data)

    def writebytes(self, data):
        logger.debug("Mock SPI wrote %s bytes", len(data))

    def writebytes2(self, data):
        self.writebytes(data)

    def close(self):
        return None


class MockGPIO:
    BCM = 0
    OUT = 2
    IN = 3
    HIGH = 1
    LOW = 0
    PUD_DOWN = 21

    @staticmethod
    def setwarnings(enabled):
        return None

    @staticmethod
    def setmode(mode):
        return None

    @staticmethod
    def setup(pin, mode, **kwargs):
        return None

    @staticmethod
    def output(pin, value):
        return None

    @staticmethod
    def input(pin):
        return 0  # Waveshare V2 and V4 BUSY are active-high; zero is idle.

    @staticmethod
    def cleanup(pin=None):
        return None


class GPIOZeroGPIO:
    """Small GPIO-module facade backed by gpiozero's character-device API.

    This matches Waveshare's current Raspberry Pi transport. Keeping the
    facade shaped like RPi.GPIO lets the controller drivers remain transport
    agnostic while retaining RPi.GPIO as a compatibility fallback.
    """

    BCM = 0
    OUT = 2
    IN = 3
    HIGH = 1
    LOW = 0
    PUD_OFF = 20
    PUD_DOWN = 21
    PUD_UP = 22

    def __init__(self):
        from gpiozero import Button, DigitalInputDevice, LED

        self._button_type = Button
        self._input_type = DigitalInputDevice
        self._led_type = LED
        self._inputs = {}
        self._outputs = {}

    @staticmethod
    def setwarnings(enabled):
        return None

    @staticmethod
    def setmode(mode):
        return None

    def setup(self, pin, mode, **kwargs):
        self.cleanup(pin)
        if mode == self.OUT:
            self._outputs[pin] = self._led_type(pin)
            return
        if mode == self.IN:
            pull = kwargs.get("pull_up_down", self.PUD_OFF)
            if pull == self.PUD_DOWN:
                device = self._button_type(pin, pull_up=False)
            elif pull == self.PUD_UP:
                device = self._button_type(pin, pull_up=True)
            else:
                device = self._input_type(
                    pin,
                    pull_up=None,
                    active_state=True,
                )
            self._inputs[pin] = device
            return
        raise ValueError(f"Unsupported GPIO mode: {mode!r}")

    def output(self, pin, value):
        device = self._outputs[pin]
        if value:
            device.on()
        else:
            device.off()

    def input(self, pin):
        return int(self._inputs[pin].value)

    def cleanup(self, pin=None):
        pins = set(self._inputs) | set(self._outputs) if pin is None else {pin}
        for selected_pin in pins:
            device = self._inputs.pop(selected_pin, None)
            if device is None:
                device = self._outputs.pop(selected_pin, None)
            if device is not None:
                device.close()


class Waveshare2in13Base(EInkDeviceInterface):
    """Common SPI/GPIO lifecycle for versioned 2.13-inch drivers."""

    # Hardware smoke tests may require a completed BUSY cycle only from
    # drivers that declare this capability.
    CONFIRMS_REFRESH_WITH_BUSY = True

    # Public, landscape canvas used by DisplayManager.
    WIDTH = 250
    HEIGHT = 122

    # Native controller memory geometry shared by V2 and V4.
    NATIVE_WIDTH = 122
    NATIVE_HEIGHT = 250
    LINE_BYTES = (NATIVE_WIDTH + 7) // 8
    FRAME_BYTES = LINE_BYTES * NATIVE_HEIGHT

    width = WIDTH
    height = HEIGHT

    DRIVER_OUTPUT_CONTROL = 0x01
    DEEP_SLEEP_MODE = 0x10
    DATA_ENTRY_MODE_SETTING = 0x11
    SW_RESET = 0x12
    MASTER_ACTIVATION = 0x20
    DISPLAY_UPDATE_CONTROL_1 = 0x21
    DISPLAY_UPDATE_CONTROL_2 = 0x22
    WRITE_RAM = 0x24
    BORDER_WAVEFORM_CONTROL = 0x3C
    SET_RAM_X_ADDRESS_START_END_POSITION = 0x44
    SET_RAM_Y_ADDRESS_START_END_POSITION = 0x45
    SET_RAM_X_ADDRESS_COUNTER = 0x4E
    SET_RAM_Y_ADDRESS_COUNTER = 0x4F
    RESET_HIGH_SECONDS = 0.2
    RESET_LOW_SECONDS = 0.005
    SLEEP_VALUE = 0x01

    def __init__(self):
        self.initialized = False
        self._closed = False
        self.last_refresh_confirmed_by_busy = None
        self.reset_pin = 17
        self.dc_pin = 25
        self.busy_pin = 24
        self.cs_pin = 8
        self.power_pin = 18

        try:
            import spidev

            try:
                self.GPIO = GPIOZeroGPIO()
                self.gpio_backend = "gpiozero"
            except ImportError:
                import RPi.GPIO as gpio

                self.GPIO = gpio
                self.gpio_backend = "RPi.GPIO"
            self.SPI = spidev.SpiDev()
            self.hardware_available = True
            logger.info(
                "Hardware libraries loaded successfully (GPIO: %s)",
                self.gpio_backend,
            )
        except ImportError:
            self.GPIO = MockGPIO
            self.SPI = MockSpiDev()
            self.gpio_backend = "mock"
            self.hardware_available = False
            logger.warning("Hardware libraries unavailable; transport is mock-only")

    @staticmethod
    def _load_rpi_gpio():
        import RPi.GPIO as gpio

        return gpio

    def _setup_gpio(self):
        self.GPIO.setwarnings(False)
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setup(self.reset_pin, self.GPIO.OUT)
        self.GPIO.setup(self.dc_pin, self.GPIO.OUT)
        # Waveshare's gpiozero transport biases the active-high BUSY input low.
        self.GPIO.setup(
            self.busy_pin,
            self.GPIO.IN,
            pull_up_down=self.GPIO.PUD_DOWN,
        )
        self.GPIO.setup(self.power_pin, self.GPIO.OUT)
        self.GPIO.output(self.power_pin, self.GPIO.HIGH)

    def _initialize_transport(self):
        """Power the HAT and open SPI0 without choosing a controller."""
        self._closed = False
        try:
            self._setup_gpio()
        except Exception:
            if self.gpio_backend != "gpiozero":
                raise
            logger.warning(
                "gpiozero could not claim the display pins; trying RPi.GPIO",
                exc_info=True,
            )
            try:
                self.GPIO.cleanup()
            except Exception:
                logger.debug("gpiozero cleanup failed", exc_info=True)
            self.GPIO = self._load_rpi_gpio()
            self.gpio_backend = "RPi.GPIO"
            self._setup_gpio()

        if self.hardware_available:
            try:
                self.SPI.open(0, 0)
                self.SPI.max_speed_hz = 4_000_000
                self.SPI.mode = 0
            except Exception:
                self.hardware_available = False
                self.initialized = False
                self.SPI.close()
                raise

    @abstractmethod
    def init(self):
        """Initialize the controller using the selected panel revision."""
        raise NotImplementedError

    def reset(self):
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        time.sleep(self.RESET_HIGH_SECONDS)
        self.GPIO.output(self.reset_pin, self.GPIO.LOW)
        time.sleep(self.RESET_LOW_SECONDS)
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        time.sleep(self.RESET_HIGH_SECONDS)

    def send_command(self, command: int):
        self.GPIO.output(self.dc_pin, self.GPIO.LOW)
        self.SPI.writebytes([command])

    def send_data(self, data: int | Iterable[int]):
        self.GPIO.output(self.dc_pin, self.GPIO.HIGH)
        payload = [data] if isinstance(data, int) else list(data)
        if len(payload) > 1 and hasattr(self.SPI, "writebytes2"):
            self.SPI.writebytes2(payload)
        else:
            self.SPI.writebytes(payload)

    def wait_until_idle(
        self,
        timeout: float = 30.0,
        poll_interval: float = 0.01,
        *,
        require_busy: bool = False,
        busy_assert_timeout: float = 1.0,
    ):
        """Wait for active-high BUSY and optionally prove a refresh started."""
        if require_busy:
            self.last_refresh_confirmed_by_busy = False
            assert_deadline = time.monotonic() + busy_assert_timeout
            while self.GPIO.input(self.busy_pin) != self.GPIO.HIGH:
                if time.monotonic() >= assert_deadline:
                    raise TimeoutError(
                        "E-Ink BUSY did not assert; check panel power and "
                        "FPC/HAT seating"
                    )
                time.sleep(poll_interval)

        deadline = time.monotonic() + timeout
        while self.GPIO.input(self.busy_pin) == self.GPIO.HIGH:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"E-Ink BUSY remained high for {timeout:g} seconds")
            time.sleep(poll_interval)
        if require_busy:
            self.last_refresh_confirmed_by_busy = True

    def wait_for_refresh(
        self,
        timeout: float = 30.0,
        poll_interval: float = 0.01,
        *,
        busy_assert_timeout: float = 1.0,
        fallback_timeout: float = 30.0,
    ) -> bool:
        """Wait for a complete BUSY cycle, or conservatively hold power.

        Returns ``True`` only when the controller's BUSY assertion and release
        were both observed. If no leading edge arrives within the grace
        period, power remains asserted for ``fallback_timeout`` seconds and
        the result is ``False``.
        """
        assert_deadline = time.monotonic() + busy_assert_timeout
        while self.GPIO.input(self.busy_pin) != self.GPIO.HIGH:
            if time.monotonic() >= assert_deadline:
                logger.warning(
                    "E-Ink BUSY did not assert; using %.1fs refresh fallback",
                    fallback_timeout,
                )
                time.sleep(fallback_timeout)
                return False
            time.sleep(poll_interval)

        self.wait_until_idle(timeout=timeout, poll_interval=poll_interval)
        return True

    def _set_window(self, x_start: int, y_start: int, x_end: int, y_end: int):
        self.send_command(self.SET_RAM_X_ADDRESS_START_END_POSITION)
        self.send_data((x_start >> 3) & 0xFF)
        self.send_data((x_end >> 3) & 0xFF)

        self.send_command(self.SET_RAM_Y_ADDRESS_START_END_POSITION)
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    def _set_cursor(self, x: int, y: int):
        self.send_command(self.SET_RAM_X_ADDRESS_COUNTER)
        self.send_data(x & 0xFF)
        self.send_command(self.SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)

    @abstractmethod
    def _update(self):
        raise NotImplementedError

    @abstractmethod
    def _image_buffer(self, image: Image.Image) -> bytearray:
        raise NotImplementedError

    def _prepare_frame_write(self):
        self._set_window(0, 0, self.NATIVE_WIDTH - 1, self.NATIVE_HEIGHT - 1)
        self._set_cursor(0, 0)

    def clear(self):
        if not self.initialized:
            self.init()
        self.display_bytes(bytes([0xFF]) * self.FRAME_BYTES)

    def display_image(self, image):
        if not isinstance(image, Image.Image):
            raise TypeError("display_image requires a PIL Image")
        self.display_bytes(self._image_buffer(image))
        return True

    def display_bytes(self, image_bytes):
        payload = bytes(image_bytes)
        if len(payload) != self.FRAME_BYTES:
            raise ValueError(
                f"Incorrect framebuffer size: expected {self.FRAME_BYTES} bytes, "
                f"got {len(payload)}"
            )
        if not self.initialized:
            self.init()

        self._prepare_frame_write()
        self.send_command(self.WRITE_RAM)
        self.send_data(payload)
        self._update()

    def getbuffer(self, image):
        return self._image_buffer(image)

    def display(self, buffer):
        if isinstance(buffer, (bytearray, bytes, list)):
            return self.display_bytes(buffer)
        return self.display_image(buffer)

    def Clear(self, color=0xFF):
        self.display_bytes(bytes([color]) * self.FRAME_BYTES)

    def sleep(self):
        self.send_command(self.DEEP_SLEEP_MODE)
        self.send_data(self.SLEEP_VALUE)
        time.sleep(2.0)

    def close(self):
        if self._closed:
            return
        try:
            self.SPI.close()
        finally:
            try:
                self.GPIO.output(self.power_pin, self.GPIO.LOW)
            except Exception:
                logger.debug("Display power-down failed", exc_info=True)
            for pin in (
                self.reset_pin,
                self.dc_pin,
                self.busy_pin,
                self.power_pin,
            ):
                try:
                    self.GPIO.cleanup(pin)
                except Exception:
                    logger.debug(
                        "GPIO cleanup failed for pin %s",
                        pin,
                        exc_info=True,
                    )
            super().close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
