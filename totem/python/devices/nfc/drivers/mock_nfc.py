from devices.nfc.nfc import NFCDeviceInterface
from utils.logger import logger

class Driver(NFCDeviceInterface):
    def __init__(self):
        self.initialized = False
        self.stored_data = b"Mock NFC Card Data"
        
    def init(self):
        logger.info("Initializing Mock NFC reader.")
        self.initialized = True
        logger.info("Mock NFC reader initialized successfully.")

    def read(self) -> bytes:
        if not self.initialized:
            raise RuntimeError("Mock NFC driver not initialized.")
        logger.info("Reading data from Mock NFC card.")
        return self.stored_data

    def write(self, data: bytes):
        if not self.initialized:
            raise RuntimeError("Mock NFC driver not initialized.")
        logger.info(f"Writing data to Mock NFC card: {data}")
        self.stored_data = data
        logger.info("Data written successfully to Mock NFC card.") 