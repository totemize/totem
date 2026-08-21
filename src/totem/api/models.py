"""Typed request, response, and event contracts for the Totem API."""

from enum import Enum
from typing import Any, Dict, List, Optional

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
    WIFI_RADIO_STATE_CHANGED = "wifi_radio_state_changed"
    BLUETOOTH_RADIO_STATE_CHANGED = "bluetooth_radio_state_changed"
    WIFI_P2P_PEER_FOUND = "wifi_p2p_peer_found"
    WIFI_P2P_PEER_LOST = "wifi_p2p_peer_lost"
    WIFI_P2P_GROUP_FORMED = "wifi_p2p_group_formed"
    WIFI_P2P_GROUP_REMOVED = "wifi_p2p_group_removed"
    BLE_ADVERTISEMENT_FOUND = "ble_advertisement_found"
    BLE_ADVERTISEMENT_UPDATED = "ble_advertisement_updated"
    BLE_ADVERTISEMENT_EXPIRED = "ble_advertisement_expired"
    BLE_CONNECTION_CHANGED = "ble_connection_changed"
    GATT_NOTIFICATION = "gatt_notification"
    BLE_L2CAP_CONNECTION_OPENED = "ble_l2cap_connection_opened"
    BLE_L2CAP_CONNECTION_CLOSED = "ble_l2cap_connection_closed"
    BLE_L2CAP_CONNECTION_HANDED_OFF = "ble_l2cap_connection_handed_off"


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


class DisplayImageRequest(BaseModel):
    image_base64: str


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


class OperationSupportResponse(BaseModel):
    supported: bool
    reason: Optional[str] = None


class WiFiAwareCapabilitiesResponse(BaseModel):
    discovery: OperationSupportResponse
    data_path: OperationSupportResponse
    interface_mode: Optional[str] = None


class L2CAPCapabilitiesResponse(BaseModel):
    le_coc_listen: OperationSupportResponse
    le_coc_connect: OperationSupportResponse
    fd_handoff: OperationSupportResponse
    maximum_listeners: int = Field(ge=0)
    maximum_connections: int = Field(ge=0)


class RadioBlockResponse(BaseModel):
    soft_blocked: bool
    hard_blocked: bool


class PhysicalRadioResponse(BaseModel):
    id: str
    kind: str
    interfaces: List[str]
    driver: Optional[str] = None
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    bus_info: Optional[str] = None


class InterfaceLimitResponse(BaseModel):
    modes: List[str]
    maximum: int


class ConcurrentInterfaceCombinationResponse(BaseModel):
    limits: List[InterfaceLimitResponse]
    maximum_interfaces: int
    maximum_channels: int


class WiFiCapabilitiesResponse(BaseModel):
    radios: List[PhysicalRadioResponse]
    bands: Dict[str, List[int]]
    interface_modes: List[str]
    concurrent_combinations: List[ConcurrentInterfaceCombinationResponse]
    operations: Dict[str, OperationSupportResponse]
    aware: WiFiAwareCapabilitiesResponse


class BluetoothCapabilitiesResponse(BaseModel):
    adapter: str
    address: str
    address_type: Optional[str] = None
    name: Optional[str] = None
    version: Optional[int] = None
    manufacturer: Optional[int] = None
    modalias: Optional[str] = None
    roles: List[str]
    supported_advertisement_instances: int
    active_advertisement_instances: int
    supported_advertisement_includes: List[str]
    maximum_advertisement_length: Optional[int] = None
    maximum_scan_response_length: Optional[int] = None
    operations: Dict[str, OperationSupportResponse]
    l2cap: L2CAPCapabilitiesResponse


class NetworkCapabilitiesResponse(BaseModel):
    wifi: WiFiCapabilitiesResponse
    bluetooth: BluetoothCapabilitiesResponse


class WiFiRadioResponse(BaseModel):
    enabled: bool
    hardware_enabled: bool
    block: RadioBlockResponse


class BluetoothRadioResponse(BaseModel):
    powered: bool
    discovering: bool
    discoverable: bool
    pairable: bool
    block: RadioBlockResponse


class RadioRequest(BaseModel):
    enabled: bool
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class WiFiInterfaceResponse(BaseModel):
    interface: str
    mode: Optional[str] = None
    state: str
    connection: Optional[str] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None
    addresses: List[str]


class WiFiNetworkResponse(BaseModel):
    ssid: str
    signal_percent: int = Field(ge=0, le=100)
    security: Optional[str] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None


class WiFiConnectionRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(default="", max_length=256)
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)


class P2PDiscoveryRequest(BaseModel):
    duration_seconds: int = Field(default=30, ge=1, le=600)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class P2PPeerResponse(BaseModel):
    id: str
    path: str
    address: str
    name: Optional[str] = None
    strength: int = Field(ge=0, le=100)
    last_seen_monotonic: int
    flags: int
    manufacturer: Optional[str] = None
    model: Optional[str] = None


class P2PGroupRequest(BaseModel):
    peer_id: str = Field(min_length=1)
    timeout_seconds: float = Field(default=45.0, gt=0, le=180)


class P2PGroupResponse(BaseModel):
    id: str
    active_connection_path: str
    connection_path: str
    role: Optional[str] = None
    peer_address: Optional[str] = None
    interface: Optional[str] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None
    addresses: List[str]
    state: str


class BLEAdvertisementResponse(BaseModel):
    id: str
    path: str
    type: str
    service_uuids: List[str]
    local_name: Optional[str] = None
    includes: List[str]
    registered_at: str


class NetworkStatusResponse(BaseModel):
    wifi_radio: WiFiRadioResponse
    wifi_interfaces: List[WiFiInterfaceResponse]
    p2p_discovering: bool
    p2p_groups: List[P2PGroupResponse]
    bluetooth_radio: BluetoothRadioResponse
    bluetooth_discovery_sessions: int
    bluetooth_advertisements: List[BLEAdvertisementResponse]


class BLEDiscoveryRequest(BaseModel):
    duration_seconds: int = Field(default=30, ge=1, le=600)
    service_uuids: List[str] = Field(default_factory=list)
    duplicate_data: bool = True
    session_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class BLEDiscoveryResponse(BaseModel):
    session_id: str


class BLEDeviceResponse(BaseModel):
    id: str
    path: str
    address: str
    address_type: Optional[str] = None
    name: Optional[str] = None
    service_uuids: List[str]
    service_data: Dict[str, str]
    manufacturer_data: Dict[str, str]
    rssi: Optional[int] = None
    tx_power: Optional[int] = None
    first_seen_at: str
    last_seen_at: str
    connected: bool
    paired: bool
    services_resolved: bool


class BLEAdvertisementRequest(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    type: str = Field(default="peripheral", pattern="^(peripheral|broadcast)$")
    service_uuids: List[str] = Field(default_factory=list)
    service_data_base64: Dict[str, str] = Field(default_factory=dict)
    manufacturer_data_base64: Dict[int, str] = Field(default_factory=dict)
    local_name: Optional[str] = Field(default=None, max_length=248)
    includes: List[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class L2CAPListenerRequest(BaseModel):
    service_uuid: str = Field(
        default="9c90b790-2cc5-42c0-9f87-c9cc40648f4c",
        min_length=4,
        max_length=36,
    )
    psm: int = Field(default=0, ge=0, le=255)
    mtu: int = Field(default=1024, ge=23, le=65535)
    address_type: str = Field(default="public", pattern="^(public|random)$")
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class L2CAPListenerResponse(BaseModel):
    id: str
    local_address: str
    address_type: str
    psm: int = Field(ge=1, le=255)
    mtu: int = Field(ge=23, le=65535)
    service_uuid: str
    advertisement_id: Optional[str] = None
    listening: bool


class L2CAPConnectionRequest(BaseModel):
    peer_address: str = Field(pattern="^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    psm: int = Field(ge=1, le=255)
    mtu: int = Field(default=1024, ge=23, le=65535)
    address_type: str = Field(default="public", pattern="^(public|random)$")
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class L2CAPConnectionResponse(BaseModel):
    id: str
    listener_id: Optional[str] = None
    peer_address: str
    address_type: str
    psm: int = Field(ge=1, le=255)
    mtu: int = Field(ge=23, le=65535)
    connected_at: str
    handed_off: bool


class L2CAPHandoffRequest(BaseModel):
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class BLEDeviceOperationRequest(BaseModel):
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)


class GATTCharacteristicResponse(BaseModel):
    id: str
    path: str
    uuid: str
    service_path: str
    flags: List[str]
    notifying: bool
    value_base64: Optional[str] = None


class GATTServiceResponse(BaseModel):
    id: str
    path: str
    uuid: str
    primary: bool
    characteristics: List[GATTCharacteristicResponse]


class GATTValueResponse(BaseModel):
    value_base64: str


class GATTWriteRequest(BaseModel):
    value_base64: str
    with_response: bool = True
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class GATTSubscriptionRequest(BaseModel):
    subscription_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)


class GATTSubscriptionResponse(BaseModel):
    subscription_id: str
