from devices.nfc.nfc import NFCDeviceInterface
from utils.logger import logger

class Driver(NFCDeviceInterface):
    def __init__(self):
        self.initialized = False

    def init(self):
        logger.info("Initializing PNC532 NFC reader.")
        self.initialized = True

    def read(self) -> bytes:
        if not self.initialized:
            raise RuntimeError("PNC532 driver not initialized.")
        logger.debug("Reading data from PNC532 NFC reader.")
        return b"Sample data from PNC532"

    def write(self, data: bytes):
        if not self.initialized:
            raise RuntimeError("PNC532 driver not initialized.")
        logger.debug(f"Writing data to PNC532 NFC reader: {data}")
