"""PN532 NFC reader behavior retained behind provider ownership."""

from totem.logging import logger


class Driver:
    """Compatibility-shaped PN532 implementation without legacy inheritance."""

    def __init__(self) -> None:
        self.initialized = False

    def init(self) -> None:
        logger.info("Initializing PN532 NFC reader.")
        self.initialized = True

    def read(self) -> bytes:
        if not self.initialized:
            raise RuntimeError("PN532 driver not initialized.")
        logger.debug("Reading data from PN532 NFC reader.")
        return b"Sample data from PN532"

    def write(self, data: bytes) -> None:
        if not self.initialized:
            raise RuntimeError("PN532 driver not initialized.")
        logger.debug("Writing data to PN532 NFC reader: %s", data)
