"""NetworkManager-owned Linux Wi-Fi implementation."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from dbus_next import Variant

from totem.devices.network.capabilities import (
    frequency_to_channel,
    modes_fit_combination,
    parse_iw_phy,
    parse_rfkill_json,
)
from totem.devices.network.dbus_runtime import DBusCallError, SystemDBusRuntime
from totem.devices.network.errors import (
    RadioConflictError,
    RadioOperationError,
    RadioResourceNotFoundError,
    UnsupportedFeatureError,
)
from totem.devices.network.nan import NanDiscoveryController
from totem.devices.network.models import (
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
from totem.logging import logger


NM_SERVICE = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_INTERFACE = "org.freedesktop.NetworkManager"
NM_DEVICE = "org.freedesktop.NetworkManager.Device"
NM_WIFI_P2P = "org.freedesktop.NetworkManager.Device.WifiP2P"
NM_P2P_PEER = "org.freedesktop.NetworkManager.WifiP2PPeer"
NM_ACTIVE = "org.freedesktop.NetworkManager.Connection.Active"
NM_IP4 = "org.freedesktop.NetworkManager.IP4Config"
CAP_NET_ADMIN = 12


def _process_has_net_admin() -> bool:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return True
    try:
        status = Path("/proc/self/status").read_text()
    except OSError:
        return False
    match = re.search(r"^CapEff:\s*([0-9a-fA-F]+)$", status, re.MULTILINE)
    return bool(match and int(match.group(1), 16) & (1 << CAP_NET_ADMIN))


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in ("/usr/sbin", "/usr/bin", "/sbin", "/bin"):
        candidate = Path(directory) / name
        if candidate.exists():
            return str(candidate)
    return name


def _split_nmcli(line: str) -> List[str]:
    values: List[str] = []
    current = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            values.append("".join(current))
            current = []
        else:
            current.append(character)
    values.append("".join(current))
    return values


class NetworkManagerWiFiDriver(WiFiDeviceInterface):
    def __init__(
        self,
        interface: str,
        runtime: Optional[SystemDBusRuntime] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.interface = interface
        self.initialized = False
        self._runtime = runtime
        self._owns_runtime = runtime is None
        self._event_callback = event_callback
        self._p2p_path: Optional[str] = None
        self._p2p_discovering = False
        self._p2p_discovery_timer: Optional[threading.Timer] = None
        self._managed_groups: Dict[str, P2PGroup] = {}
        self._nan: Optional[NanDiscoveryController] = None

    def set_event_callback(self, callback) -> None:
        self._event_callback = callback

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self._event_callback:
            self._event_callback(event_type, data)

    def init(self):
        if self.initialized:
            return
        if self._runtime is None:
            self._runtime = SystemDBusRuntime()
        self._runtime.add_message_handler(self._on_message)
        self._p2p_path = self._find_p2p_device(required=False)
        self.initialized = True

    def _require_ready(self) -> None:
        if not self.initialized or self._runtime is None:
            raise RadioOperationError("Wi-Fi driver is not initialized")

    def _run(self, args: List[str], timeout: float = 15.0) -> str:
        try:
            result = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout
        except subprocess.TimeoutExpired as exc:
            from totem.devices.network.errors import RadioTimeoutError

            raise RadioTimeoutError("Wi-Fi command timed out") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or "command failed"
            raise RadioOperationError(
                "Wi-Fi operation failed: {}".format(str(detail).strip())
            ) from exc

    def _find_p2p_device(self, required: bool = True) -> Optional[str]:
        self._require_runtime()
        paths = self._runtime.call(NM_SERVICE, NM_PATH, NM_INTERFACE, "GetAllDevices")[
            0
        ]
        for path in paths:
            try:
                self._runtime.get_all(NM_SERVICE, path, NM_WIFI_P2P)
                return path
            except DBusCallError:
                continue
        if required:
            raise UnsupportedFeatureError("NetworkManager exposes no Wi-Fi P2P device")
        return None

    def _require_runtime(self) -> None:
        if self._runtime is None:
            raise RadioOperationError("System D-Bus runtime is not initialized")

    def _p2p_device(self) -> str:
        self._require_ready()
        if not self._p2p_path:
            self._p2p_path = self._find_p2p_device(required=True)
        return self._p2p_path

    def scan_networks(self, timeout: float = 20.0) -> List[WiFiNetwork]:
        self._require_ready()
        output = self._run(
            [
                _tool("nmcli"),
                "-t",
                "-e",
                "yes",
                "-f",
                "SSID,SIGNAL,SECURITY,FREQ,CHAN",
                "device",
                "wifi",
                "list",
                "ifname",
                self.interface,
                "--rescan",
                "yes",
            ],
            timeout,
        )
        networks = []
        for line in output.splitlines():
            fields = _split_nmcli(line)
            if len(fields) != 5 or not fields[0]:
                continue
            frequency = int(fields[3]) if fields[3].isdigit() else None
            networks.append(
                WiFiNetwork(
                    ssid=fields[0],
                    signal_percent=int(fields[1]) if fields[1].isdigit() else 0,
                    security=fields[2] or None,
                    frequency_mhz=frequency,
                    channel=(
                        int(fields[4])
                        if fields[4].isdigit()
                        else frequency_to_channel(frequency)
                    ),
                )
            )
        return networks

    def connect(self, ssid: str, password: str, timeout: float = 30.0):
        self._require_ready()
        args = [_tool("nmcli"), "device", "wifi", "connect", ssid]
        if password:
            args.extend(["password", password])
        args.extend(["ifname", self.interface])
        try:
            self._run(args, timeout)
        except RadioOperationError as exc:
            # Do not propagate CalledProcessError.command because it contains the PSK.
            raise RadioOperationError(
                "Failed to connect the requested Wi-Fi network"
            ) from exc
        logger.info("Connected interface %s to Wi-Fi network %r", self.interface, ssid)

    def create_hotspot(self, ssid: str, password: str, timeout: float = 30.0):
        self._require_ready()
        args = [
            _tool("nmcli"),
            "device",
            "wifi",
            "hotspot",
            "ifname",
            self.interface,
            "ssid",
            ssid,
        ]
        if password:
            args.extend(["password", password])
        try:
            self._run(args, timeout)
        except RadioOperationError as exc:
            raise RadioOperationError(
                "Failed to create the requested Wi-Fi hotspot"
            ) from exc
        logger.info("Created Wi-Fi hotspot %r on %s", ssid, self.interface)

    def disconnect(self, timeout: float = 15.0):
        self._require_ready()
        self._run([_tool("nmcli"), "device", "disconnect", self.interface], timeout)

    def get_status(self) -> str:
        states = {item.interface: item for item in self.list_interfaces()}
        state = states.get(self.interface)
        if state is None:
            return "unavailable"
        return (
            "{} ({})".format(state.state, state.connection)
            if state.connection
            else state.state
        )

    def get_radio_state(self) -> WiFiRadioState:
        self._require_ready()
        enabled = bool(
            self._runtime.get_property(
                NM_SERVICE, NM_PATH, NM_INTERFACE, "WirelessEnabled"
            )
        )
        hardware = bool(
            self._runtime.get_property(
                NM_SERVICE, NM_PATH, NM_INTERFACE, "WirelessHardwareEnabled"
            )
        )
        block = self._rfkill_state()
        return WiFiRadioState(enabled=enabled, hardware_enabled=hardware, block=block)

    def set_radio_enabled(self, enabled: bool, timeout: float = 15.0) -> WiFiRadioState:
        self._require_ready()
        before = self.get_radio_state()
        if before.enabled == enabled:
            return before
        self._runtime.set_property(
            NM_SERVICE, NM_PATH, NM_INTERFACE, "WirelessEnabled", "b", enabled, timeout
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self.get_radio_state()
            if current.enabled == enabled:
                self._emit("wifi_radio_state_changed", {"enabled": enabled})
                return current
            time.sleep(0.1)
        from totem.devices.network.errors import RadioTimeoutError

        raise RadioTimeoutError("Timed out waiting for Wi-Fi radio state change")

    def _rfkill_state(self) -> RadioBlockState:
        try:
            return parse_rfkill_json(self._run([_tool("rfkill"), "--json"]), "wlan")
        except RadioOperationError:
            enabled = bool(
                self._runtime.get_property(
                    NM_SERVICE, NM_PATH, NM_INTERFACE, "WirelessEnabled"
                )
            )
            hardware = bool(
                self._runtime.get_property(
                    NM_SERVICE, NM_PATH, NM_INTERFACE, "WirelessHardwareEnabled"
                )
            )
            return RadioBlockState(soft_blocked=not enabled, hard_blocked=not hardware)

    def get_capabilities(self) -> WiFiCapabilities:
        self._require_ready()
        phy_name = self._phy_name()
        iw_output = self._run([_tool("iw"), "phy", phy_name, "info"])
        modes, bands, combinations = parse_iw_phy(iw_output)
        driver_info = self._driver_info()
        p2p_supported = self._p2p_path is not None and "P2P-device" in modes
        nan_mode = next((mode for mode in modes if mode.upper() == "NAN"), None)
        nan_mode_supported = nan_mode is not None
        nan_privileged = _process_has_net_admin()
        nan_supported = nan_mode_supported and nan_privileged
        if not nan_mode_supported:
            nan_reason = "nl80211 NAN interface mode absent"
        elif not nan_privileged:
            nan_reason = "CAP_NET_ADMIN unavailable for nl80211 NAN lifecycle"
        else:
            nan_reason = None
        nan_data_mode = next(
            (
                mode
                for mode in modes
                if re.sub(r"[^a-z]", "", mode.lower()) == "nandata"
            ),
            None,
        )
        if not nan_mode_supported:
            nan_data_reason = "nl80211 NAN interface mode absent"
        elif nan_data_mode is None:
            nan_data_reason = "nl80211 NAN data interface mode absent"
        else:
            nan_data_reason = "Linux NAN data-path negotiation backend unavailable"
        operations = {
            "radio_toggle": OperationSupport(True),
            "infrastructure_scan": OperationSupport(True),
            "station": OperationSupport(
                "managed" in modes,
                None if "managed" in modes else "managed mode absent",
            ),
            "hotspot": OperationSupport(
                "AP" in modes, None if "AP" in modes else "AP mode absent"
            ),
            "p2p_discovery": OperationSupport(
                p2p_supported,
                None if p2p_supported else "NetworkManager P2P device absent",
            ),
            "p2p_group": OperationSupport(
                p2p_supported,
                None if p2p_supported else "NetworkManager P2P device absent",
            ),
            "nan_discovery": OperationSupport(nan_supported, nan_reason),
            "nan_data_path": OperationSupport(False, nan_data_reason),
        }
        return WiFiCapabilities(
            radios=[
                PhysicalRadio(
                    id=phy_name,
                    kind="wifi",
                    interfaces=[self.interface],
                    driver=driver_info.get("driver"),
                    driver_version=driver_info.get("version"),
                    firmware_version=driver_info.get("firmware-version"),
                    bus_info=driver_info.get("bus-info"),
                )
            ],
            bands=bands,
            interface_modes=modes,
            concurrent_combinations=combinations,
            operations=operations,
            aware=WiFiAwareCapabilities(
                discovery=operations["nan_discovery"],
                data_path=operations["nan_data_path"],
                interface_mode=nan_mode,
                data_interface_mode=nan_data_mode,
            ),
        )

    def _phy_name(self) -> str:
        try:
            return (
                Path("/sys/class/net/{}/phy80211/name".format(self.interface))
                .read_text()
                .strip()
            )
        except OSError:
            return "phy0"

    def _preflight_nan(self) -> None:
        capabilities = self.get_capabilities()
        support = capabilities.aware.discovery
        if not support.supported:
            raise UnsupportedFeatureError(
                support.reason or "Wi-Fi Aware discovery is unsupported"
            )
        active_modes = [
            interface.mode
            for interface in self.list_interfaces()
            if interface.state in ("connected", "connecting") and interface.mode
        ]
        can_run = any(
            modes_fit_combination(active_modes, "NAN", combination)
            for combination in capabilities.concurrent_combinations
        )
        if capabilities.concurrent_combinations and not can_run:
            raise RadioConflictError(
                "Active Wi-Fi interfaces do not fit a supported NAN concurrency combination"
            )

    def start_nan_discovery(
        self,
        service_name: str,
        service_info: bytes = b"",
        duration_seconds: int = 300,
        timeout: float = 15.0,
    ):
        self._require_ready()
        self._preflight_nan()
        if self._nan is None:
            self._nan = NanDiscoveryController(
                phy_name=self._phy_name(),
                interface="totemnan0",
                iw_path=_tool("iw"),
                runner=lambda arguments, command_timeout: self._run(
                    arguments, command_timeout
                ),
                event_callback=self._emit,
            )
        return self._nan.start_session(
            service_name=service_name,
            service_info=service_info,
            duration_seconds=duration_seconds,
            timeout=timeout,
        )

    def stop_nan_discovery(self, session_id: str, timeout: float = 15.0):
        self._require_ready()
        if self._nan is not None:
            return self._nan.stop_session(session_id, timeout)

    def list_nan_discovery_sessions(self):
        return self._nan.list_sessions() if self._nan is not None else []

    def list_nan_matches(self, session_id: Optional[str] = None):
        return self._nan.list_matches(session_id) if self._nan is not None else []

    def create_nan_data_path(
        self, match_id: str, port: int = 4873, timeout: float = 30.0
    ):
        support = self.get_capabilities().aware.data_path
        raise UnsupportedFeatureError(
            support.reason or "Wi-Fi Aware data paths are unsupported"
        )

    def list_nan_data_paths(self):
        return []

    def remove_nan_data_path(self, data_path_id: str, timeout: float = 15.0):
        support = self.get_capabilities().aware.data_path
        raise UnsupportedFeatureError(
            support.reason or "Wi-Fi Aware data paths are unsupported"
        )

    def _driver_info(self) -> Dict[str, str]:
        try:
            output = self._run([_tool("ethtool"), "-i", self.interface])
        except RadioOperationError:
            return {}
        result = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    def list_interfaces(self) -> List[WiFiInterfaceState]:
        self._require_ready()
        states: Dict[str, Dict[str, Optional[str]]] = {}
        output = self._run(
            [
                _tool("nmcli"),
                "-t",
                "-e",
                "yes",
                "-f",
                "DEVICE,TYPE,STATE,CONNECTION",
                "device",
                "status",
            ]
        )
        for line in output.splitlines():
            fields = _split_nmcli(line)
            if len(fields) >= 4 and fields[1] in ("wifi", "wifi-p2p"):
                states[fields[0]] = {
                    "state": fields[2],
                    "connection": fields[3] or None,
                }
        iw_modes: Dict[str, Dict[str, Optional[int]]] = {}
        try:
            iw_output = self._run([_tool("iw"), "dev"])
            current = None
            for line in iw_output.splitlines():
                stripped = line.strip()
                if stripped.startswith("Interface "):
                    current = stripped.split(None, 1)[1]
                    iw_modes[current] = {"mode": None, "frequency": None}
                elif current and stripped.startswith("type "):
                    iw_modes[current]["mode"] = stripped.split(None, 1)[1]
                elif current and stripped.startswith("channel "):
                    match = re.search(r"\((\d+)\s+MHz\)", stripped)
                    if match:
                        iw_modes[current]["frequency"] = int(match.group(1))
        except RadioOperationError:
            pass
        addresses: Dict[str, List[str]] = {}
        try:
            for item in json.loads(self._run([_tool("ip"), "-j", "address", "show"])):
                addresses[item["ifname"]] = [
                    "{}/{}".format(address["local"], address["prefixlen"])
                    for address in item.get("addr_info", [])
                ]
        except (RadioOperationError, ValueError, KeyError):
            pass
        names = sorted(set(states) | set(iw_modes))
        return [
            WiFiInterfaceState(
                interface=name,
                mode=iw_modes.get(name, {}).get("mode"),
                state=str(states.get(name, {}).get("state") or "unknown"),
                connection=states.get(name, {}).get("connection"),
                frequency_mhz=iw_modes.get(name, {}).get("frequency"),
                channel=frequency_to_channel(iw_modes.get(name, {}).get("frequency")),
                addresses=addresses.get(name, []),
            )
            for name in names
        ]

    def start_p2p_discovery(
        self, duration_seconds: int = 30, timeout: float = 15.0
    ) -> None:
        if not 1 <= duration_seconds <= 600:
            raise ValueError("P2P discovery duration must be between 1 and 600 seconds")
        path = self._p2p_device()
        if self._p2p_discovering:
            return
        self._runtime.call(
            NM_SERVICE,
            path,
            NM_WIFI_P2P,
            "StartFind",
            "a{sv}",
            [{"timeout": Variant("i", duration_seconds)}],
            timeout,
        )
        self._p2p_discovering = True
        self._p2p_discovery_timer = threading.Timer(
            duration_seconds, self._expire_p2p_discovery
        )
        self._p2p_discovery_timer.daemon = True
        self._p2p_discovery_timer.start()

    def _expire_p2p_discovery(self) -> None:
        try:
            self.stop_p2p_discovery()
        except RadioOperationError:
            # NetworkManager also enforces the discovery timeout, so expiry may
            # race its own StopFind. Local state still must become inactive.
            self._p2p_discovering = False
            self._p2p_discovery_timer = None

    def stop_p2p_discovery(self, timeout: float = 15.0) -> None:
        if not self._p2p_discovering:
            return
        path = self._p2p_device()
        try:
            self._runtime.call(
                NM_SERVICE, path, NM_WIFI_P2P, "StopFind", timeout=timeout
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith(("NotFound", "NotActive", "Failed")):
                raise
        finally:
            self._p2p_discovering = False
            timer = self._p2p_discovery_timer
            self._p2p_discovery_timer = None
            if timer is not None:
                timer.cancel()

    def is_p2p_discovering(self) -> bool:
        return self._p2p_discovering

    @staticmethod
    def _peer_id(address: str) -> str:
        return address.lower().replace(":", "_")

    def _peer_from_path(self, path: str) -> P2PPeer:
        properties = self._runtime.get_all(NM_SERVICE, path, NM_P2P_PEER)
        address = str(properties.get("HwAddress", ""))
        return P2PPeer(
            id=self._peer_id(address),
            path=path,
            address=address,
            name=properties.get("Name") or None,
            strength=int(properties.get("Strength", 0)),
            last_seen_monotonic=int(properties.get("LastSeen", -1)),
            flags=int(properties.get("Flags", 0)),
            manufacturer=properties.get("Manufacturer") or None,
            model=properties.get("Model") or None,
        )

    def list_p2p_peers(self) -> List[P2PPeer]:
        path = self._p2p_device()
        paths = self._runtime.get_property(NM_SERVICE, path, NM_WIFI_P2P, "Peers") or []
        peers = []
        for peer_path in paths:
            try:
                peers.append(self._peer_from_path(peer_path))
            except DBusCallError:
                continue
        return peers

    def _preflight_p2p(self) -> None:
        capabilities = self.get_capabilities()
        active_modes = [
            interface.mode
            for interface in self.list_interfaces()
            if interface.state in ("connected", "connecting")
            and interface.mode
            and interface.mode != "P2P-device"
        ]
        can_client = any(
            modes_fit_combination(active_modes, "P2P-client", combination)
            for combination in capabilities.concurrent_combinations
        )
        can_go = any(
            modes_fit_combination(active_modes, "P2P-GO", combination)
            for combination in capabilities.concurrent_combinations
        )
        if capabilities.concurrent_combinations and not (can_client or can_go):
            raise RadioConflictError(
                "Active Wi-Fi interfaces do not fit a supported P2P concurrency combination"
            )

    def create_p2p_group(self, peer_id: str, timeout: float = 45.0) -> P2PGroup:
        self._preflight_p2p()
        peers = {peer.id: peer for peer in self.list_p2p_peers()}
        peer = peers.get(peer_id.lower())
        if peer is None:
            raise RadioResourceNotFoundError("Wi-Fi Direct peer was not found")
        connection_id = "totem-p2p-{}".format(uuid.uuid4().hex[:12])
        settings = {
            "connection": {
                "id": Variant("s", connection_id),
                "type": Variant("s", "wifi-p2p"),
                "autoconnect": Variant("b", False),
            },
            "wifi-p2p": {"peer": Variant("s", peer.address)},
            "ipv4": {"method": Variant("s", "link-local")},
            "ipv6": {"method": Variant("s", "link-local")},
        }
        result = self._runtime.call(
            NM_SERVICE,
            NM_PATH,
            NM_INTERFACE,
            "AddAndActivateConnection2",
            "a{sa{sv}}ooa{sv}",
            [
                settings,
                self._p2p_device(),
                peer.path,
                {
                    "persist": Variant("s", "volatile"),
                    "bind-activation": Variant("s", "dbus-client"),
                },
            ],
            timeout,
        )
        connection_path, active_path = result[0], result[1]
        group = self._group_from_active(active_path, connection_path, peer.address)
        self._managed_groups[group.id] = group
        self._emit(
            "wifi_p2p_group_formed", {"group_id": group.id, "peer": peer.address}
        )
        return group

    def _group_from_active(
        self,
        active_path: str,
        connection_path: Optional[str] = None,
        peer_address: Optional[str] = None,
    ) -> P2PGroup:
        props = self._runtime.get_all(NM_SERVICE, active_path, NM_ACTIVE)
        devices = props.get("Devices", [])
        interface = None
        frequency = None
        addresses: List[str] = []
        role = None
        for device_path in devices:
            device = self._runtime.get_all(NM_SERVICE, device_path, NM_DEVICE)
            interface = (
                device.get("IpInterface") or device.get("Interface") or interface
            )
            if interface:
                matching = [
                    item
                    for item in self.list_interfaces()
                    if item.interface == interface
                ]
                if matching:
                    role = matching[0].mode
                    frequency = matching[0].frequency_mhz
                    addresses = matching[0].addresses
        state_number = int(props.get("State", 0))
        state = P2PGroupState.ACTIVE if state_number == 2 else P2PGroupState.ACTIVATING
        group_id = active_path.rsplit("/", 1)[-1]
        return P2PGroup(
            id=group_id,
            active_connection_path=active_path,
            connection_path=connection_path or str(props.get("Connection", "/")),
            role=role,
            peer_address=peer_address,
            interface=interface,
            frequency_mhz=frequency,
            channel=frequency_to_channel(frequency),
            addresses=addresses,
            state=state,
        )

    def list_p2p_groups(self) -> List[P2PGroup]:
        self._require_ready()
        active_paths = (
            self._runtime.get_property(
                NM_SERVICE, NM_PATH, NM_INTERFACE, "ActiveConnections"
            )
            or []
        )
        groups = []
        for active_path in active_paths:
            try:
                props = self._runtime.get_all(NM_SERVICE, active_path, NM_ACTIVE)
                if props.get("Type") == "wifi-p2p":
                    known = self._managed_groups.get(active_path.rsplit("/", 1)[-1])
                    groups.append(
                        self._group_from_active(
                            active_path,
                            known.connection_path if known else None,
                            known.peer_address if known else None,
                        )
                    )
            except DBusCallError:
                continue
        self._managed_groups = {group.id: group for group in groups}
        return groups

    def remove_p2p_group(self, group_id: str, timeout: float = 15.0) -> None:
        groups = {group.id: group for group in self.list_p2p_groups()}
        group = groups.get(group_id)
        if group is None:
            self._managed_groups.pop(group_id, None)
            return
        try:
            self._runtime.call(
                NM_SERVICE,
                NM_PATH,
                NM_INTERFACE,
                "DeactivateConnection",
                "o",
                [group.active_connection_path],
                timeout,
            )
        except DBusCallError as exc:
            if not exc.error_name.endswith(("UnknownConnection", "NotActive")):
                raise
        finally:
            self._managed_groups.pop(group_id, None)
            self._emit("wifi_p2p_group_removed", {"group_id": group_id})

    def _on_message(self, message) -> None:
        if message.interface != NM_WIFI_P2P or not message.body:
            return
        if message.member == "PeerAdded":
            # This callback runs on the D-Bus loop thread. Do not synchronously
            # call back into that loop for peer properties; consumers can use
            # list_p2p_peers() after receiving the path-only notification.
            self._emit("wifi_p2p_peer_found", {"path": message.body[0]})
        elif message.member == "PeerRemoved":
            self._emit("wifi_p2p_peer_lost", {"path": message.body[0]})

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        if self.initialized:
            if self._nan is not None:
                self._nan.close()
            try:
                self.stop_p2p_discovery()
            except RadioOperationError:
                pass
            for group_id in list(self._managed_groups):
                try:
                    self.remove_p2p_group(group_id)
                except RadioOperationError:
                    pass
            if self._runtime:
                self._runtime.remove_message_handler(self._on_message)
                if self._owns_runtime:
                    self._runtime.close()
        super().close()
