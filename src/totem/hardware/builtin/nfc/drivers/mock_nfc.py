"""Explicit in-memory NFC driver used only when mock mode is selected."""

from totem.logging import logger


class Driver:
    """Preserve the legacy mock card's stateful, in-memory behavior exactly."""

    IS_MOCK = True

    def __init__(self) -> None:
        self.initialized = False
        self.stored_data = b"Mock NFC Card Data"

    def init(self) -> None:
        logger.info("Initializing Mock NFC reader.")
        self.initialized = True
        logger.info("Mock NFC reader initialized successfully.")

    def read(self) -> bytes:
        if not self.initialized:
            raise RuntimeError("Mock NFC driver not initialized.")
        logger.info("Reading data from Mock NFC card.")
        return self.stored_data

    def write(self, data: bytes) -> None:
        if not self.initialized:
            raise RuntimeError("Mock NFC driver not initialized.")
        logger.info("Writing data to Mock NFC card: %s", data)
        self.stored_data = data
        logger.info("Data written successfully to Mock NFC card.")

    def poll(self) -> bool:
        """The in-memory card is always present after explicit mock selection."""

        return True
