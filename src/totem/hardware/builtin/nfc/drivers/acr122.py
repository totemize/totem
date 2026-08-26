"""ACR122 NFC reader behavior retained behind provider ownership."""

from totem.logging import logger


class Driver:
    """Compatibility-shaped ACR122 implementation without legacy inheritance."""

    def __init__(self) -> None:
        self.initialized = False

    def init(self) -> None:
        logger.info("Initializing ACS ACR122 NFC reader.")
        self.initialized = True

    def read(self) -> bytes:
        if not self.initialized:
            raise RuntimeError("ACS ACR122 driver not initialized.")
        logger.debug("Reading data from ACS ACR122 NFC reader.")
        return b"Sample data from ACS ACR122"

    def write(self, data: bytes) -> None:
        if not self.initialized:
            raise RuntimeError("ACS ACR122 driver not initialized.")
        logger.debug("Writing data to ACS ACR122 NFC reader: %s", data)
