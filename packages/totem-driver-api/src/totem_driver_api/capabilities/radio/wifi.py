"""Data-only public contract for Wi-Fi connection operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ...identifiers import CapabilityId, ContractError


WIFI_CONNECTION = CapabilityId("wifi.connection", 1)


def _text(value: object, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ContractError("wifi {} must be a non-empty string".format(field))
    return value.strip()


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal_dbm: int
    secure: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "ssid", _text(self.ssid, "ssid"))
        if isinstance(self.signal_dbm, bool) or not isinstance(self.signal_dbm, int):
            raise ContractError("wifi signal_dbm must be an integer")
        if not isinstance(self.secure, bool):
            raise ContractError("wifi secure must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"ssid": self.ssid, "signal_dbm": self.signal_dbm, "secure": self.secure}


@dataclass(frozen=True)
class WifiScanRequest:
    def to_json_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True)
class WifiScanResult:
    networks: Tuple[WifiNetwork, ...]

    def __post_init__(self) -> None:
        networks = tuple(self.networks)
        if not all(isinstance(network, WifiNetwork) for network in networks):
            raise ContractError("wifi networks must contain WifiNetwork values")
        object.__setattr__(self, "networks", networks)

    def to_json_value(self) -> dict[str, object]:
        return {"networks": [network.to_json_value() for network in self.networks]}


@dataclass(frozen=True)
class WifiConnectRequest:
    ssid: str
    password: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ssid", _text(self.ssid, "ssid"))
        if self.password is not None:
            object.__setattr__(self, "password", _text(self.password, "password", allow_empty=True))

    def to_json_value(self) -> dict[str, object]:
        value: dict[str, object] = {"ssid": self.ssid}
        if self.password is not None:
            value["password"] = self.password
        return value


@dataclass(frozen=True)
class WifiConnectResult:
    connected: bool
    ssid: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.connected, bool):
            raise ContractError("wifi connected must be boolean")
        if self.ssid is not None:
            object.__setattr__(self, "ssid", _text(self.ssid, "ssid"))

    def to_json_value(self) -> dict[str, object]:
        value: dict[str, object] = {"connected": self.connected}
        if self.ssid is not None:
            value["ssid"] = self.ssid
        return value


@dataclass(frozen=True)
class WifiDisconnectRequest:
    def to_json_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True)
class WifiDisconnectResult:
    disconnected: bool

    def __post_init__(self) -> None:
        if not isinstance(self.disconnected, bool):
            raise ContractError("wifi disconnected must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"disconnected": self.disconnected}


@dataclass(frozen=True)
class WifiHotspotRequest:
    ssid: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ssid", _text(self.ssid, "ssid"))

    def to_json_value(self) -> dict[str, object]:
        return {"ssid": self.ssid}


@dataclass(frozen=True)
class WifiHotspotResult:
    active: bool

    def __post_init__(self) -> None:
        if not isinstance(self.active, bool):
            raise ContractError("wifi hotspot active must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"active": self.active}


@dataclass(frozen=True)
class WifiStatusPush:
    connected: bool
    ssid: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.connected, bool):
            raise ContractError("wifi connected must be boolean")
        if self.ssid is not None:
            object.__setattr__(self, "ssid", _text(self.ssid, "ssid"))

    @property
    def type(self) -> str:
        return "wifi.connection.status"

    def to_json_value(self) -> dict[str, object]:
        return WifiConnectResult(self.connected, self.ssid).to_json_value()
