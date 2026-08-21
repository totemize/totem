"""Policy-free radio capability and state contracts.

The device layer reports what the hardware and system radio stacks can do.  It
does not decide when a Totem should discover or connect to another device.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WiFiMode(str, Enum):
    STATION = "managed"
    AP = "AP"
    P2P_CLIENT = "P2P-client"
    P2P_GO = "P2P-GO"
    P2P_DEVICE = "P2P-device"
    IBSS = "IBSS"
    MONITOR = "monitor"
    NAN = "NAN"
    NAN_DATA = "NAN-data"


class P2PGroupState(str, Enum):
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationSupport:
    supported: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class WiFiAwareCapabilities:
    discovery: OperationSupport
    followup: OperationSupport
    data_path: OperationSupport
    interface_mode: Optional[str] = None
    data_interface_mode: Optional[str] = None


@dataclass(frozen=True)
class L2CAPCapabilities:
    le_coc_listen: OperationSupport
    le_coc_connect: OperationSupport
    fd_handoff: OperationSupport
    maximum_listeners: int
    maximum_connections: int


@dataclass(frozen=True)
class RadioBlockState:
    soft_blocked: bool
    hard_blocked: bool


@dataclass(frozen=True)
class PhysicalRadio:
    id: str
    kind: str
    interfaces: List[str] = field(default_factory=list)
    driver: Optional[str] = None
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    bus_info: Optional[str] = None


@dataclass(frozen=True)
class InterfaceLimit:
    modes: List[str]
    maximum: int


@dataclass(frozen=True)
class ConcurrentInterfaceCombination:
    limits: List[InterfaceLimit]
    maximum_interfaces: int
    maximum_channels: int


@dataclass(frozen=True)
class WiFiCapabilities:
    radios: List[PhysicalRadio]
    bands: Dict[str, List[int]]
    interface_modes: List[str]
    concurrent_combinations: List[ConcurrentInterfaceCombination]
    operations: Dict[str, OperationSupport]
    aware: WiFiAwareCapabilities


@dataclass(frozen=True)
class WiFiRadioState:
    enabled: bool
    hardware_enabled: bool
    block: RadioBlockState


@dataclass(frozen=True)
class WiFiInterfaceState:
    interface: str
    mode: Optional[str]
    state: str
    connection: Optional[str] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None
    addresses: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class WiFiNetwork:
    ssid: str
    signal_percent: int
    security: Optional[str] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None


@dataclass(frozen=True)
class P2PPeer:
    id: str
    path: str
    address: str
    name: Optional[str]
    strength: int
    last_seen_monotonic: int
    flags: int = 0
    manufacturer: Optional[str] = None
    model: Optional[str] = None


@dataclass(frozen=True)
class P2PGroup:
    id: str
    active_connection_path: str
    connection_path: str
    role: Optional[str]
    peer_address: Optional[str]
    interface: Optional[str]
    frequency_mhz: Optional[int]
    channel: Optional[int]
    addresses: List[str]
    state: P2PGroupState


@dataclass(frozen=True)
class NanDiscoverySession:
    id: str
    interface: str
    service_name: str
    publish_cookie: int
    subscribe_cookie: int
    service_info_base64: str
    started_at: str
    duration_seconds: int
    active: bool


@dataclass(frozen=True)
class NanMatch:
    id: str
    session_id: str
    peer_address: str
    local_instance_id: int
    peer_instance_id: int
    service_info_base64: str
    last_seen_at: str


@dataclass(frozen=True)
class NanFollowup:
    id: str
    session_id: str
    match_id: str
    peer_address: str
    local_instance_id: int
    peer_instance_id: int
    payload_base64: str
    direction: str
    created_at: str


@dataclass(frozen=True)
class NanDataPath:
    id: str
    match_id: str
    interface: str
    peer_address: str
    local_ipv6: str
    peer_ipv6: str
    port: int
    state: str
    created_at: str


@dataclass(frozen=True)
class BluetoothCapabilities:
    adapter: str
    address: str
    address_type: Optional[str]
    name: Optional[str]
    version: Optional[int]
    manufacturer: Optional[int]
    modalias: Optional[str]
    roles: List[str]
    supported_advertisement_instances: int
    active_advertisement_instances: int
    supported_advertisement_includes: List[str]
    maximum_advertisement_length: Optional[int]
    maximum_scan_response_length: Optional[int]
    operations: Dict[str, OperationSupport]
    l2cap: L2CAPCapabilities


@dataclass(frozen=True)
class BluetoothRadioState:
    powered: bool
    discovering: bool
    discoverable: bool
    pairable: bool
    block: RadioBlockState


@dataclass(frozen=True)
class BLEDevice:
    id: str
    path: str
    address: str
    address_type: Optional[str]
    name: Optional[str]
    service_uuids: List[str]
    service_data: Dict[str, str]
    manufacturer_data: Dict[str, str]
    rssi: Optional[int]
    tx_power: Optional[int]
    first_seen_at: str
    last_seen_at: str
    connected: bool
    paired: bool
    services_resolved: bool


@dataclass(frozen=True)
class BLEAdvertisement:
    id: str
    path: str
    type: str
    service_uuids: List[str]
    local_name: Optional[str]
    includes: List[str]
    registered_at: str


@dataclass(frozen=True)
class L2CAPListener:
    id: str
    local_address: str
    address_type: str
    psm: int
    mtu: int
    service_uuid: str
    advertisement_id: Optional[str]
    listening: bool


@dataclass(frozen=True)
class L2CAPConnection:
    id: str
    listener_id: Optional[str]
    peer_address: str
    address_type: str
    psm: int
    mtu: int
    connected_at: str
    handed_off: bool = False


@dataclass(frozen=True)
class GATTCharacteristic:
    id: str
    path: str
    uuid: str
    service_path: str
    flags: List[str]
    notifying: bool
    value_base64: Optional[str] = None


@dataclass(frozen=True)
class GATTService:
    id: str
    path: str
    uuid: str
    primary: bool
    characteristics: List[GATTCharacteristic]


@dataclass(frozen=True)
class NetworkCapabilities:
    wifi: WiFiCapabilities
    bluetooth: BluetoothCapabilities


@dataclass(frozen=True)
class NetworkStatus:
    wifi_radio: WiFiRadioState
    wifi_interfaces: List[WiFiInterfaceState]
    p2p_discovering: bool
    p2p_groups: List[P2PGroup]
    nan_discovery_sessions: List[NanDiscoverySession]
    nan_data_paths: List[NanDataPath]
    bluetooth_radio: BluetoothRadioState
    bluetooth_discovery_sessions: int
    bluetooth_advertisements: List[BLEAdvertisement]


def serialize(value: Any) -> Any:
    """Convert nested radio dataclasses and enums into JSON-compatible data."""

    if hasattr(value, "__dataclass_fields__"):
        return serialize(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    return value
