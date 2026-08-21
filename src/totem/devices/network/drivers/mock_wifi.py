"""Deterministic mock with parity to the complete Wi-Fi contract."""

import base64
from datetime import datetime, timezone
import time
import threading
from typing import Any, Callable, Dict, Optional
import uuid

from totem.devices.network.errors import RadioResourceNotFoundError
from totem.devices.network.models import (
    ConcurrentInterfaceCombination,
    InterfaceLimit,
    NanDataPath,
    NanDiscoverySession,
    NanMatch,
    OperationSupport,
    P2PGroup,
    P2PGroupState,
    P2PPeer,
    PhysicalRadio,
    RadioBlockState,
    WiFiCapabilities,
    WiFiAwareCapabilities,
    WiFiInterfaceState,
    WiFiNetwork,
    WiFiRadioState,
)
from totem.devices.network.network import WiFiDeviceInterface


class Driver(WiFiDeviceInterface):
    IS_MOCK = True

    def __init__(self):
        self.initialized = False
        self.radio_enabled = True
        self.connected = False
        self.current_ssid: Optional[str] = None
        self.hotspot_active = False
        self.hotspot_ssid: Optional[str] = None
        self.p2p_discovering = False
        self._p2p_discovery_timer: Optional[threading.Timer] = None
        self.groups: Dict[str, P2PGroup] = {}
        self.nan_sessions: Dict[str, NanDiscoverySession] = {}
        self.nan_matches: Dict[str, NanMatch] = {}
        self.nan_data_paths: Dict[str, NanDataPath] = {}
        self._nan_cookie = 1
        self._event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_callback:
            self._event_callback(event_type, data)

    def _ready(self):
        if not self.initialized:
            raise RuntimeError("Mock Wi-Fi driver is not initialized")

    def init(self):
        self.initialized = True

    def scan_networks(self, timeout: float = 20.0):
        self._ready()
        return [
            WiFiNetwork("Home_Network", 82, "WPA2", 2412, 1),
            WiFiNetwork("Office_WiFi", 61, "WPA2", 2437, 6),
        ]

    def connect(self, ssid: str, password: str, timeout: float = 30.0):
        self._ready()
        self.connected = True
        self.current_ssid = ssid
        self.hotspot_active = False
        self.hotspot_ssid = None

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        self._ready()
        self.connected = False
        self.current_ssid = None
        self.hotspot_active = True
        self.hotspot_ssid = ssid

    def disconnect(self, timeout: float = 15.0):
        self._ready()
        self.connected = False
        self.current_ssid = None
        self.hotspot_active = False
        self.hotspot_ssid = None

    def get_status(self) -> str:
        self._ready()
        if self.connected:
            return "connected ({})".format(self.current_ssid)
        if self.hotspot_active:
            return "connected ({})".format(self.hotspot_ssid)
        return "disconnected"

    def get_radio_state(self):
        self._ready()
        return WiFiRadioState(
            enabled=self.radio_enabled,
            hardware_enabled=True,
            block=RadioBlockState(
                soft_blocked=not self.radio_enabled, hard_blocked=False
            ),
        )

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0):
        self._ready()
        changed = enabled != self.radio_enabled
        self.radio_enabled = enabled
        if changed:
            self._emit("wifi_radio_state_changed", {"enabled": enabled})
        return self.get_radio_state()

    def get_capabilities(self):
        self._ready()
        supported = OperationSupport(True)
        return WiFiCapabilities(
            radios=[PhysicalRadio("phy-mock", "wifi", ["wlan-mock"], "mock")],
            bands={"band1": list(range(1, 14))},
            interface_modes=[
                "managed",
                "AP",
                "P2P-client",
                "P2P-GO",
                "P2P-device",
                "NAN",
                "NAN-data",
            ],
            concurrent_combinations=[
                ConcurrentInterfaceCombination(
                    limits=[
                        InterfaceLimit(["managed"], 2),
                        InterfaceLimit(["P2P-device"], 1),
                        InterfaceLimit(["P2P-client", "P2P-GO"], 1),
                    ],
                    maximum_interfaces=3,
                    maximum_channels=2,
                )
            ],
            operations={
                "radio_toggle": supported,
                "infrastructure_scan": supported,
                "station": supported,
                "hotspot": supported,
                "p2p_discovery": supported,
                "p2p_group": supported,
                "nan_discovery": supported,
                "nan_data_path": supported,
            },
            aware=WiFiAwareCapabilities(
                discovery=supported,
                data_path=supported,
                interface_mode="NAN",
                data_interface_mode="NAN-data",
            ),
        )

    def list_interfaces(self):
        self._ready()
        interfaces = []
        if self.connected or self.hotspot_active:
            interfaces.append(
                WiFiInterfaceState(
                    interface="wlan-mock",
                    mode="managed" if self.connected else "AP",
                    state="connected",
                    connection=self.current_ssid or self.hotspot_ssid,
                    frequency_mhz=2412,
                    channel=1,
                    addresses=["192.0.2.10/24"],
                )
            )
        if self.p2p_discovering:
            interfaces.append(
                WiFiInterfaceState("p2p-dev-wlan-mock", "P2P-device", "disconnected")
            )
        if self.nan_sessions:
            interfaces.append(WiFiInterfaceState("totemnan0", "NAN", "connected"))
        for data_path in self.nan_data_paths.values():
            interfaces.append(
                WiFiInterfaceState(
                    data_path.interface,
                    "NAN-data",
                    "connected",
                    addresses=[data_path.local_ipv6],
                )
            )
        return interfaces

    def start_p2p_discovery(self, duration_seconds: int = 30, timeout: float = 15.0):
        self._ready()
        if not 1 <= duration_seconds <= 600:
            raise ValueError("P2P discovery duration must be between 1 and 600 seconds")
        self.p2p_discovering = True
        self._emit("wifi_p2p_peer_found", {"peer_id": "02_00_00_00_00_02"})
        self._p2p_discovery_timer = threading.Timer(
            duration_seconds, self.stop_p2p_discovery
        )
        self._p2p_discovery_timer.daemon = True
        self._p2p_discovery_timer.start()

    def stop_p2p_discovery(self, timeout: float = 15.0):
        self._ready()
        self.p2p_discovering = False
        timer = self._p2p_discovery_timer
        self._p2p_discovery_timer = None
        if timer is not None:
            timer.cancel()

    def is_p2p_discovering(self) -> bool:
        return self.p2p_discovering

    def list_p2p_peers(self):
        self._ready()
        return [
            P2PPeer(
                id="02_00_00_00_00_02",
                path="/mock/p2p/peer/2",
                address="02:00:00:00:00:02",
                name="mock-totem",
                strength=77,
                last_seen_monotonic=int(time.monotonic()),
            )
        ]

    def create_p2p_group(self, peer_id: str, timeout: float = 45.0):
        self._ready()
        peers = {peer.id: peer for peer in self.list_p2p_peers()}
        peer = peers.get(peer_id.lower())
        if peer is None:
            raise RadioResourceNotFoundError("Wi-Fi Direct peer was not found")
        group_id = uuid.uuid4().hex[:8]
        group = P2PGroup(
            id=group_id,
            active_connection_path="/mock/p2p/group/{}".format(group_id),
            connection_path="/mock/p2p/connection/{}".format(group_id),
            role="P2P-client",
            peer_address=peer.address,
            interface="p2p-wlan-mock-0",
            frequency_mhz=2412,
            channel=1,
            addresses=["169.254.10.2/16"],
            state=P2PGroupState.ACTIVE,
        )
        self.groups[group_id] = group
        self._emit("wifi_p2p_group_formed", {"group_id": group_id})
        return group

    def list_p2p_groups(self):
        self._ready()
        return list(self.groups.values())

    def remove_p2p_group(self, group_id: str, timeout: float = 15.0):
        self._ready()
        if self.groups.pop(group_id, None) is not None:
            self._emit("wifi_p2p_group_removed", {"group_id": group_id})

    def start_nan_discovery(
        self,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ):
        self._ready()
        session_id = uuid.uuid4().hex
        publish_cookie = self._nan_cookie
        subscribe_cookie = self._nan_cookie + 1
        self._nan_cookie += 2
        now = datetime.now(timezone.utc).isoformat()
        session = NanDiscoverySession(
            id=session_id,
            interface="totemnan0",
            service_name=service_name,
            publish_cookie=publish_cookie,
            subscribe_cookie=subscribe_cookie,
            service_info_base64=base64.b64encode(service_info).decode("ascii"),
            started_at=now,
            duration_seconds=duration_seconds,
            active=True,
        )
        match_id = "{}_02_00_00_00_20_02".format(session_id)
        match = NanMatch(
            id=match_id,
            session_id=session_id,
            peer_address="02:00:00:00:20:02",
            local_instance_id=1,
            peer_instance_id=2,
            service_info_base64=base64.b64encode(b"mock-peer").decode("ascii"),
            last_seen_at=now,
        )
        self.nan_sessions[session_id] = session
        self.nan_matches[match_id] = match
        self._emit(
            "wifi_nan_match_found",
            {
                "match_id": match_id,
                "session_id": session_id,
                "peer_address": match.peer_address,
            },
        )
        return session

    def stop_nan_discovery(self, session_id: str, timeout: float = 15.0):
        self.nan_sessions.pop(session_id, None)
        self.nan_matches = {
            key: value
            for key, value in self.nan_matches.items()
            if value.session_id != session_id
        }

    def list_nan_discovery_sessions(self):
        return list(self.nan_sessions.values())

    def list_nan_matches(self, session_id: Optional[str] = None):
        if session_id and session_id not in self.nan_sessions:
            raise RadioResourceNotFoundError("NAN discovery session was not found")
        return [
            value
            for value in self.nan_matches.values()
            if session_id is None or value.session_id == session_id
        ]

    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        self._ready()
        match = self.nan_matches.get(match_id)
        if match is None:
            raise RadioResourceNotFoundError("NAN match was not found")
        path_id = uuid.uuid4().hex[:8]
        interface = "aware_data{}".format(len(self.nan_data_paths))
        path = NanDataPath(
            id=path_id,
            match_id=match_id,
            interface=interface,
            peer_address=match.peer_address,
            local_ipv6="fe80::1%{}".format(interface),
            peer_ipv6="fe80::2%{}".format(interface),
            port=port,
            state="active",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.nan_data_paths[path_id] = path
        self._emit(
            "wifi_nan_data_path_ready",
            {
                "data_path_id": path_id,
                "interface": interface,
                "peer_ipv6": path.peer_ipv6,
                "port": port,
            },
        )
        return path

    def list_nan_data_paths(self):
        return list(self.nan_data_paths.values())

    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        if self.nan_data_paths.pop(data_path_id, None) is not None:
            self._emit("wifi_nan_data_path_removed", {"data_path_id": data_path_id})

    def close(self):
        if getattr(self, "_closed", False):
            return
        if self.initialized:
            self.stop_p2p_discovery()
        elif self._p2p_discovery_timer is not None:
            self._p2p_discovery_timer.cancel()
            self._p2p_discovery_timer = None
        self.groups.clear()
        self.nan_sessions.clear()
        self.nan_matches.clear()
        self.nan_data_paths.clear()
        super().close()
