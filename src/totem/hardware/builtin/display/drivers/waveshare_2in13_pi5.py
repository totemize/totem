"""Pi 5 Waveshare 2.13-inch controller using the SPI hardware chip select."""

import time

from .waveshare_2in13_v1 import Driver as _V1Driver


class Pi5Driver(_V1Driver):
    """V1 controller protocol with an injected Pi 5 transport boundary."""

    TRANSPORT_KIND = "pi5-hardware-cs"
    USE_SOFTWARE_CHIP_SELECT = False

    def __init__(self, *, spi: object = None, gpio: object = None, sleep=time.sleep) -> None:
        super().__init__(spi=spi, gpio=gpio, sleep=sleep)
        self.cs_pin = 8


class Driver(Pi5Driver):
    """Concrete Pi 5 hardware-chip-select variant."""


__all__ = ["Driver"]
