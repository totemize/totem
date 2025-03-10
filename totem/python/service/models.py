from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
import time
import json


class DeviceType(str, Enum):
    DISPLAY = "display"
    NFC = "nfc"
    STORAGE = "storage"
    NETWORK = "network"


class DeviceId(BaseModel):
    device_type: DeviceType
    device_id: str = "default"  # Default device ID if not specified


class Status(BaseModel):
    success: bool
    message: str


class DeviceState(BaseModel):
    device: DeviceId
    state: Dict[str, Any] = Field(default_factory=dict)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


class DeviceCommand(BaseModel):
    device: DeviceId
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    def to_json(self) -> str:
        return json.dumps(self.model_dump())
    
    @staticmethod
    def from_json(json_str: str) -> "DeviceCommand":
        data = json.loads(json_str)
        return DeviceCommand(**data)


class EventType(str, Enum):
    STATE_CHANGE = "state_change"
    COMMAND_COMPLETED = "command_completed"
    ERROR = "error"
    DATA_AVAILABLE = "data_available"
    HARDWARE_EVENT = "hardware_event"


class DeviceEvent(BaseModel):
    device: DeviceId
    event_type: EventType
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    
    def to_json(self) -> str:
        return json.dumps(self.model_dump())
    
    @staticmethod
    def from_json(json_str: str) -> "DeviceEvent":
        data = json.loads(json_str)
        return DeviceEvent(**data)


# Display-specific models
class DisplayTextRequest(BaseModel):
    device_id: str = "default"
    text: str
    font_size: int = 24
    position: Dict[str, Any] = Field(default_factory=dict)


class DisplayImageRequest(BaseModel):
    device_id: str = "default"
    image_data: bytes
    format: str = "png"
    position: Dict[str, Any] = Field(default_factory=dict)


# NFC-specific models
class NFCDataRequest(BaseModel):
    device_id: str = "default"
    data: Optional[bytes] = None
    format: str = "raw"


# Storage-specific models
class StorageOperationRequest(BaseModel):
    device_id: str = "default"
    path: str
    data: Optional[bytes] = None


# Network-specific models
class NetworkConfigurationRequest(BaseModel):
    device_id: str = "default"
    ssid: str
    password: str
    is_hotspot: bool = False 