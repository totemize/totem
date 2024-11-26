from devices.nfc.nfc import NFC
from utils.logger import logger

class NFCManager:
    def __init__(self, driver_name: str = None):
        self.nfc_device = NFC(driver_name)
        self.nfc_device.initialize()

    def read_card(self) -> str:
        try:
            data = self.nfc_device.read_data()
            logger.info("Successfully read data from NFC card.")
            return data.decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading NFC card: {e}")
            raise

    def write_card(self, data: str):
        try:
            self.nfc_device.write_data(data.encode('utf-8'))
            logger.info("Successfully wrote data to NFC card.")
        except Exception as e:
            logger.error(f"Error writing to NFC card: {e}")
            raise
