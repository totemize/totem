
import unittest
from devices.nfc.nfc import NFC
from devices.nfc.drivers.pnc532 import Driver as PNC532Driver

class TestNFC(unittest.TestCase):
    def test_pnc532_initialization(self):
        nfc = NFC('pnc532')
        nfc.initialize()
        self.assertTrue(nfc.driver.initialized)

    def test_pnc532_read(self):
        nfc = NFC('pnc532')
        nfc.initialize()
        data = nfc.read_data()
        self.assertEqual(data, b"Sample data from PNC532")