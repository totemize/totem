"""Deterministic mock with parity to the complete Wi-Fi contract."""

import time
import threading
from typing import Any, Callable, Dict, Optional
import uuid

from totem.devices.network.errors import RadioResourceNotFoundError
from totem.devices.network.models import (
    ConcurrentInterfaceCombination,
    InterfaceLimit,
    OperationSupport,
    P2PGroup,
    P2PGroupState,
    P2PPeer,
    PhysicalRadio,
    RadioBlockState,
    WiFiCapabilities,
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
            interface_modes=["managed", "AP", "P2P-client", "P2P-GO", "P2P-device"],
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
            },
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

    def close(self):
        if getattr(self, "_closed", False):
            return
        if self.initialized:
            self.stop_p2p_discovery()
        elif self._p2p_discovery_timer is not None:
            self._p2p_discovery_timer.cancel()
            self._p2p_discovery_timer = None
        self.groups.clear()
        super().close()
