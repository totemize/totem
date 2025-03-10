"""
Service package for Totem hardware control.
Contains modules for device services, event management, and data models.
"""

# Import main components for easy access
from .models import DeviceType, DeviceId, DeviceState, DeviceCommand, DeviceEvent, EventType
from .event_manager import EventManager
from .device_service import DeviceService 