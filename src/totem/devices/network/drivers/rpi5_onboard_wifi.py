from totem.devices.network.drivers.network_manager_wifi import NetworkManagerWiFiDriver


class Driver(NetworkManagerWiFiDriver):
    def __init__(self):
        super().__init__("wlan0")
