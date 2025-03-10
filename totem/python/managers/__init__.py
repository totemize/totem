"""
Managers package for Totem hardware components.
Contains modules for managing different hardware devices.
"""

# Import managers for easy access
from .display_manager import DisplayManager
from .nfc_manager import NFCManager
from .network_manager import NetworkManager
from .storage_manager import StorageManager
# from .nvme_manager import NVMeManager  # This class doesn't exist yet 