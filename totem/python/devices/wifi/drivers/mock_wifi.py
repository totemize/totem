from devices.wifi.wifi import WiFiDeviceInterface
from utils.logger import logger
import random
import time

class Driver(WiFiDeviceInterface):
    def __init__(self):
        self.initialized = False
        self.connected = False
        self.current_ssid = None
        self.hotspot_active = False
        self.hotspot_ssid = None
        
    def init(self):
        logger.info("Initializing Mock WiFi device.")
        self.initialized = True
        logger.info("Mock WiFi device initialized successfully.")

    def scan_networks(self) -> list:
        if not self.initialized:
            raise RuntimeError("Mock WiFi driver not initialized.")
        
        logger.info("Scanning for WiFi networks...")
        # Return mock WiFi networks
        networks = [
            "Home_Network:-45dBm",
            "Office_WiFi:-62dBm",
            "Neighbor_WiFi:-78dBm",
            "Guest_Network:-55dBm",
            "IoT_Network:-60dBm"
        ]
        logger.info(f"Found {len(networks)} mock WiFi networks")
        return networks

    def connect(self, ssid: str, password: str):
        if not self.initialized:
            raise RuntimeError("Mock WiFi driver not initialized.")
        
        logger.info(f"Connecting to WiFi network: {ssid}")
        # Simulate connection delay
        time.sleep(0.5)
        self.connected = True
        self.current_ssid = ssid
        self.hotspot_active = False
        self.hotspot_ssid = None
        logger.info(f"Successfully connected to {ssid}")

    def create_hotspot(self, ssid: str, password: str):
        if not self.initialized:
            raise RuntimeError("Mock WiFi driver not initialized.")
        
        logger.info(f"Creating WiFi hotspot: {ssid}")
        # Simulate hotspot creation delay
        time.sleep(0.5)
        self.connected = False
        self.current_ssid = None
        self.hotspot_active = True
        self.hotspot_ssid = ssid
        logger.info(f"WiFi hotspot {ssid} created successfully")

    def disconnect(self):
        if not self.initialized:
            raise RuntimeError("Mock WiFi driver not initialized.")
        
        if self.connected:
            logger.info(f"Disconnecting from WiFi network: {self.current_ssid}")
            self.connected = False
            self.current_ssid = None
        elif self.hotspot_active:
            logger.info(f"Stopping WiFi hotspot: {self.hotspot_ssid}")
            self.hotspot_active = False
            self.hotspot_ssid = None
        else:
            logger.info("No active WiFi connection or hotspot to disconnect")

    def get_status(self) -> str:
        if not self.initialized:
            raise RuntimeError("Mock WiFi driver not initialized.")
        
        if self.connected:
            signal_strength = random.randint(-70, -30)
            return f"Connected to {self.current_ssid}, Signal: {signal_strength}dBm"
        elif self.hotspot_active:
            clients = random.randint(0, 5)
            return f"Hotspot {self.hotspot_ssid} active with {clients} client(s)"
        else:
            return "Disconnected" 