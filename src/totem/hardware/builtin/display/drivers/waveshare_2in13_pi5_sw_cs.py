"""Pi 5 Waveshare 2.13-inch controller with software chip select."""

from .waveshare_2in13_pi5 import Pi5Driver


class Driver(Pi5Driver):
    """Keep chip select active around every Pi 5 SPI transfer."""

    TRANSPORT_KIND = "pi5-software-cs"
    USE_SOFTWARE_CHIP_SELECT = True

    def _select_chip(self, value: int) -> None:
        self.GPIO.output(self.cs_pin, value)

    def send_command(self, command: int) -> None:
        self._select_chip(self.GPIO.LOW)
        try:
            super().send_command(command)
        finally:
            self._select_chip(self.GPIO.HIGH)

    def send_data(self, data: object) -> None:
        self._select_chip(self.GPIO.LOW)
        try:
            super().send_data(data)
        finally:
            self._select_chip(self.GPIO.HIGH)
