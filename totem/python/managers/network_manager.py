from devices.wifi.wifi import WiFi
from utils.logger import logger
from typing import Optional

class NetworkManager:
    def __init__(self, driver_name: Optional[str] = None):
        self.wifi_device = WiFi(driver_name)
        self.wifi_device.initialize()

    def scan_networks(self) -> list:
        networks = self.wifi_device.scan_networks()
        parsed_networks = []
        for network in networks:
            ssid_signal = network.split(':')
            if len(ssid_signal) == 2:
                ssid, signal = ssid_signal
                parsed_networks.append({'SSID': ssid, 'Signal': signal})
        return parsed_networks

    def connect_to_network(self, ssid: str, password: str):
        logger.info(f"Attempting to connect to Wi-Fi network '{ssid}'.")
        self.wifi_device.connect(ssid, password)

    def create_hotspot(self, ssid: str, password: str):
        logger.info(f"Creating Wi-Fi hotspot '{ssid}'.")
        self.wifi_device.create_hotspot(ssid, password)

    def stop_hotspot(self):
        logger.info("Stopping Wi-Fi hotspot.")
        self.wifi_device.disconnect()

    def get_wifi_status(self) -> str:
        status = self.wifi_device.get_status()
        logger.info(f"Current Wi-Fi status: {status}")
        return status
