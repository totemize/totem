"""Typed request, response, and event contracts for the Totem API."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    DISPLAY = "display"
    NFC = "nfc"
    STORAGE = "storage"
    NETWORK = "network"
    UPS = "ups"


class DeviceId(BaseModel):
    device_type: DeviceType
    device_id: str = "default"


class Status(BaseModel):
    success: bool
    message: str


class StorageReadResponse(Status):
    data_base64: str


class UPSStatusResponse(BaseModel):
    model: str
    battery_percent: float = Field(ge=0.0, le=100.0)
    voltage_volts: float
    current_amps: float
    power_plugged: Optional[bool] = None


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

    def to_json(self) -> str:
        return self.model_dump_json()


class DisplayTextRequest(BaseModel):
    text: str
    font_size: int = Field(default=24, gt=0)
    x: int = 10
    y: int = 10


class DisplayRefreshMode(str, Enum):
    FULL = "full"
    PARTIAL = "partial"


class DisplayImageRequest(BaseModel):
    image_base64: str
    refresh_mode: DisplayRefreshMode = DisplayRefreshMode.FULL


class NFCWriteRequest(BaseModel):
    data: str


class StorageReadRequest(BaseModel):
    path: str


class StorageWriteRequest(BaseModel):
    path: str
    data_base64: str


class NetworkConfigurationRequest(BaseModel):
    ssid: str = Field(min_length=1)
    password: str
    is_hotspot: bool = False
