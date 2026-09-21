"""Injected-transport framebuffer contract shared by Waveshare 2.13 panels."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from typing import Iterable, Optional


logger = logging.getLogger(__name__)


class MockSpiDev:
    """Minimal explicit mock transport; it never opens a physical device."""

    def open(self, bus: int, device: int) -> None:
        del bus, device

    def xfer2(self, data: Iterable[int]) -> list[int]:
        return [0 for _item in data]

    def writebytes(self, data: Iterable[int]) -> None:
        del data

    def writebytes2(self, data: Iterable[int]) -> None:
        self.writebytes(data)

    def close(self) -> None:
        return None


class MockGPIO:
    BCM, OUT, IN, HIGH, LOW, PUD_DOWN = 0, 2, 3, 1, 0, 21

    @staticmethod
    def setwarnings(enabled: bool) -> None:
        del enabled

    @staticmethod
    def setmode(mode: int) -> None:
        del mode

    @staticmethod
    def setup(pin: int, mode: int, **kwargs: object) -> None:
        del pin, mode, kwargs

    @staticmethod
    def output(pin: int, value: int) -> None:
        del pin, value

    @staticmethod
    def input(pin: int) -> int:
        del pin
        return 0

    @staticmethod
    def cleanup(pin: Optional[int] = None) -> None:
        del pin


class Waveshare2in13Base(ABC):
    """Common SPI/GPIO lifecycle without choosing a concrete controller."""

    CONFIRMS_REFRESH_WITH_BUSY = True
    WIDTH, HEIGHT = 250, 122
    NATIVE_WIDTH, NATIVE_HEIGHT = 122, 250
    LINE_BYTES = (NATIVE_WIDTH + 7) // 8
    FRAME_BYTES = LINE_BYTES * NATIVE_HEIGHT
    MOUNT_ROTATION_DEGREES = 180
    width, height = WIDTH, HEIGHT

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

    def __init__(self, *, spi: object = None, gpio: object = None, sleep=time.sleep) -> None:
        self.initialized = False
        self._closed = False
        self._sleep = sleep
        self.last_refresh_confirmed_by_busy = None
        self.reset_pin, self.dc_pin, self.busy_pin, self.cs_pin, self.power_pin = 17, 25, 24, 8, 18
        self.SPI = spi
        self.GPIO = gpio
        self.hardware_available = spi is not None and gpio is not None
        self.gpio_backend = "injected" if self.hardware_available else "unconfigured"

    def _load_default_transports(self) -> None:
        """Import hardware dependencies only when a concrete child initializes."""

        if self.SPI is not None and self.GPIO is not None:
            return
        try:
            import spidev

            try:
                from gpiozero import Button, DigitalInputDevice, LED

                self.GPIO = _GPIOZeroGPIO(Button, DigitalInputDevice, LED)
                self.gpio_backend = "gpiozero"
            except ImportError:
                import RPi.GPIO as gpio

                self.GPIO = gpio
                self.gpio_backend = "RPi.GPIO"
            self.SPI = spidev.SpiDev()
            self.hardware_available = True
        except ImportError:
            self.GPIO = MockGPIO
            self.SPI = MockSpiDev()
            self.gpio_backend = "mock"
            self.hardware_available = False
            logger.warning("Hardware libraries unavailable; transport is mock-only")

    def _setup_gpio(self) -> None:
        assert self.GPIO is not None
        self.GPIO.setwarnings(False)
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setup(self.reset_pin, self.GPIO.OUT)
        self.GPIO.setup(self.dc_pin, self.GPIO.OUT)
        self.GPIO.setup(self.busy_pin, self.GPIO.IN, pull_up_down=self.GPIO.PUD_DOWN)
        self.GPIO.setup(self.power_pin, self.GPIO.OUT)
        self.GPIO.output(self.power_pin, self.GPIO.HIGH)

    def _initialize_transport(self) -> None:
        self._closed = False
        self._load_default_transports()
        self._setup_gpio()
        assert self.SPI is not None
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
    def init(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _update(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _image_buffer(self, image: object) -> bytearray:
        raise NotImplementedError

    def reset(self) -> None:
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        self._sleep(self.RESET_HIGH_SECONDS)
        self.GPIO.output(self.reset_pin, self.GPIO.LOW)
        self._sleep(self.RESET_LOW_SECONDS)
        self.GPIO.output(self.reset_pin, self.GPIO.HIGH)
        self._sleep(self.RESET_HIGH_SECONDS)

    def send_command(self, command: int) -> None:
        self.GPIO.output(self.dc_pin, self.GPIO.LOW)
        self.SPI.writebytes([command])

    def send_data(self, data: int | Iterable[int]) -> None:
        self.GPIO.output(self.dc_pin, self.GPIO.HIGH)
        payload = [data] if isinstance(data, int) else list(data)
        if len(payload) > 1 and hasattr(self.SPI, "writebytes2"):
            self.SPI.writebytes2(payload)
        else:
            self.SPI.writebytes(payload)

    def wait_until_idle(self, timeout: float = 30.0, poll_interval: float = 0.01, *, require_busy: bool = False, busy_assert_timeout: float = 1.0) -> None:
        if require_busy:
            self.last_refresh_confirmed_by_busy = False
            assert_deadline = time.monotonic() + busy_assert_timeout
            while self.GPIO.input(self.busy_pin) != self.GPIO.HIGH:
                if time.monotonic() >= assert_deadline:
                    raise TimeoutError("E-Ink BUSY did not assert; check panel power and FPC/HAT seating")
                self._sleep(poll_interval)
        deadline = time.monotonic() + timeout
        while self.GPIO.input(self.busy_pin) == self.GPIO.HIGH:
            if time.monotonic() >= deadline:
                raise TimeoutError("E-Ink BUSY remained high for {} seconds".format(timeout))
            self._sleep(poll_interval)
        if require_busy:
            self.last_refresh_confirmed_by_busy = True

    def wait_for_refresh(self, timeout: float = 30.0, poll_interval: float = 0.01, *, busy_assert_timeout: float = 1.0, fallback_timeout: float = 30.0) -> bool:
        assert_deadline = time.monotonic() + busy_assert_timeout
        while self.GPIO.input(self.busy_pin) != self.GPIO.HIGH:
            if time.monotonic() >= assert_deadline:
                logger.warning("E-Ink BUSY did not assert; using %.1fs refresh fallback", fallback_timeout)
                self._sleep(fallback_timeout)
                return False
            self._sleep(poll_interval)
        self.wait_until_idle(timeout=timeout, poll_interval=poll_interval)
        return True

    def _set_window(self, x_start: int, y_start: int, x_end: int, y_end: int) -> None:
        self.send_command(self.SET_RAM_X_ADDRESS_START_END_POSITION)
        self.send_data((x_start >> 3) & 0xFF)
        self.send_data((x_end >> 3) & 0xFF)
        self.send_command(self.SET_RAM_Y_ADDRESS_START_END_POSITION)
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    def _set_cursor(self, x: int, y: int) -> None:
        self.send_command(self.SET_RAM_X_ADDRESS_COUNTER)
        self.send_data(x & 0xFF)
        self.send_command(self.SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)

    def _prepare_frame_write(self) -> None:
        self._set_window(0, 0, self.NATIVE_WIDTH - 1, self.NATIVE_HEIGHT - 1)
        self._set_cursor(0, 0)

    def clear(self) -> None:
        if not self.initialized:
            self.init()
        self.display_bytes(bytes([0xFF]) * self.FRAME_BYTES)

    def display_image(self, image: object) -> bool:
        self.display_bytes(self._image_buffer(image))
        return True

    def display_bytes(self, image_bytes: object) -> None:
        payload = bytes(image_bytes)
        if len(payload) != self.FRAME_BYTES:
            raise ValueError("Incorrect framebuffer size: expected {} bytes, got {}".format(self.FRAME_BYTES, len(payload)))
        if not self.initialized:
            self.init()
        self._prepare_frame_write()
        self.send_command(self.WRITE_RAM)
        self.send_data(payload)
        self._update()

    def getbuffer(self, image: object) -> bytearray:
        return self._image_buffer(image)

    def display(self, buffer: object) -> object:
        if isinstance(buffer, (bytearray, bytes, list)):
            return self.display_bytes(buffer)
        return self.display_image(buffer)

    def Clear(self, color: int = 0xFF) -> None:
        self.display_bytes(bytes([color]) * self.FRAME_BYTES)

    def sleep(self) -> None:
        self.send_command(self.DEEP_SLEEP_MODE)
        self.send_data(self.SLEEP_VALUE)
        self._sleep(2.0)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.SPI is not None:
            self.SPI.close()
        if self.GPIO is not None:
            try:
                self.GPIO.output(self.power_pin, self.GPIO.LOW)
            except Exception:
                logger.debug("Display power-down failed", exc_info=True)
            for pin in (self.reset_pin, self.dc_pin, self.busy_pin, self.power_pin):
                try:
                    self.GPIO.cleanup(pin)
                except Exception:
                    logger.debug("GPIO cleanup failed for pin %s", pin, exc_info=True)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


class _GPIOZeroGPIO:
    """RPi.GPIO-shaped injected adapter for gpiozero's character-device API."""

    BCM, OUT, IN, HIGH, LOW, PUD_OFF, PUD_DOWN, PUD_UP = 0, 2, 3, 1, 0, 20, 21, 22

    def __init__(self, button: object, input_device: object, led: object) -> None:
        self._button_type, self._input_type, self._led_type = button, input_device, led
        self._inputs: dict[int, object] = {}
        self._outputs: dict[int, object] = {}

    @staticmethod
    def setwarnings(enabled: bool) -> None:
        del enabled

    @staticmethod
    def setmode(mode: int) -> None:
        del mode

    def setup(self, pin: int, mode: int, **kwargs: object) -> None:
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
                device = self._input_type(pin, pull_up=None, active_state=True)
            self._inputs[pin] = device
            return
        raise ValueError("Unsupported GPIO mode: {!r}".format(mode))

    def output(self, pin: int, value: int) -> None:
        device = self._outputs[pin]
        (device.on if value else device.off)()

    def input(self, pin: int) -> int:
        return int(self._inputs[pin].value)

    def cleanup(self, pin: Optional[int] = None) -> None:
        pins = set(self._inputs) | set(self._outputs) if pin is None else {pin}
        for selected_pin in pins:
            device = self._inputs.pop(selected_pin, None) or self._outputs.pop(selected_pin, None)
            if device is not None:
                device.close()
