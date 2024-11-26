from devices.wifi.wifi import WiFiDeviceInterface
from utils.logger import logger
import subprocess

class Driver(WiFiDeviceInterface):
    def __init__(self):
        self.interface = 'wlan1'
        self.initialized = False

    def init(self):
        logger.info("Initializing USB Wi-Fi adapter.")
        self.initialized = True

    def scan_networks(self) -> list:
        if not self.initialized:
            raise RuntimeError("Wi-Fi device not initialized.")
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID,SIGNAL', 'dev', 'wifi', 'list', 'ifname', self.interface], text=True)
            networks = [line.strip() for line in result.strip().split('\n') if line]
            logger.debug(f"Available networks: {networks}")
            return networks
        except Exception as e:
            logger.error(f"Failed to scan networks: {e}")
            return []

    def connect(self, ssid: str, password: str):
        if not self.initialized:
            raise RuntimeError("Wi-Fi device not initialized.")
        try:
            subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password, 'ifname', self.interface], check=True)
            logger.info(f"Connected to Wi-Fi network '{ssid}' using USB adapter.")
        except Exception as e:
            logger.error(f"Failed to connect to Wi-Fi network '{ssid}': {e}")
            raise

    def create_hotspot(self, ssid: str, password: str):
        if not self.initialized:
            raise RuntimeError("Wi-Fi device not initialized.")
        try:
            subprocess.run(['nmcli', 'dev', 'wifi', 'hotspot', 'ifname', self.interface, 'ssid', ssid, 'password', password], check=True)
            logger.info(f"Created Wi-Fi hotspot '{ssid}' using USB adapter.")
        except Exception as e:
            logger.error(f"Failed to create Wi-Fi hotspot: {e}")
            raise

    def disconnect(self):
        if not self.initialized:
            raise RuntimeError("Wi-Fi device not initialized.")
        try:
            subprocess.run(['nmcli', 'dev', 'disconnect', self.interface], check=True)
            logger.info("Disconnected from Wi-Fi network (USB adapter).")
        except Exception as e:
            logger.error(f"Failed to disconnect Wi-Fi: {e}")
            raise

    def get_status(self) -> str:
        try:
            result = subprocess.check_output(['nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'device', 'status'], text=True)
            for line in result.strip().split('\n'):
                parts = line.split(':')
                if parts[0] == self.interface:
                    state = parts[1]
                    connection = parts[2]
                    status = f"{state} ({connection})" if connection else state
                    logger.debug(f"USB Wi-Fi status: {status}")
                    return status
            return "Unknown"
        except Exception as e:
            logger.error(f"Failed to get Wi-Fi status: {e}")
            return "Error"
