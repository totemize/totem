"""Data-only public contract for Bluetooth session operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ...identifiers import CapabilityId, ContractError


BLUETOOTH_SESSION = CapabilityId("bluetooth.session", 1)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("bluetooth {} must be a non-empty string".format(field))
    return value.strip()


@dataclass(frozen=True)
class BluetoothDevice:
    address: str
    name: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", _text(self.address, "address").upper())
        if self.name is not None:
            object.__setattr__(self, "name", _text(self.name, "name"))

    def to_json_value(self) -> dict[str, object]:
        value: dict[str, object] = {"address": self.address}
        if self.name is not None:
            value["name"] = self.name
        return value


@dataclass(frozen=True)
class BluetoothDiscoverRequest:
    def to_json_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True)
class BluetoothDiscoveryResult:
    devices: Tuple[BluetoothDevice, ...]

    def __post_init__(self) -> None:
        devices = tuple(self.devices)
        if not all(isinstance(device, BluetoothDevice) for device in devices):
            raise ContractError("bluetooth devices must contain BluetoothDevice values")
        object.__setattr__(self, "devices", devices)

    def to_json_value(self) -> dict[str, object]:
        return {"devices": [device.to_json_value() for device in self.devices]}


@dataclass(frozen=True)
class BluetoothAdvertisementRequest:
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "name"))

    def to_json_value(self) -> dict[str, object]:
        return {"name": self.name}


@dataclass(frozen=True)
class BluetoothAdvertisementResult:
    advertising: bool

    def __post_init__(self) -> None:
        if not isinstance(self.advertising, bool):
            raise ContractError("bluetooth advertising must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"advertising": self.advertising}


@dataclass(frozen=True)
class BluetoothStopAdvertisementRequest:
    def to_json_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True)
class BluetoothConnectRequest:
    address: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "address", _text(self.address, "address").upper())

    def to_json_value(self) -> dict[str, object]:
        return {"address": self.address}


@dataclass(frozen=True)
class BluetoothConnectResult:
    connected: bool
    address: str

    def __post_init__(self) -> None:
        if not isinstance(self.connected, bool):
            raise ContractError("bluetooth connected must be boolean")
        object.__setattr__(self, "address", _text(self.address, "address").upper())

    def to_json_value(self) -> dict[str, object]:
        return {"connected": self.connected, "address": self.address}


@dataclass(frozen=True)
class BluetoothEventPush:
    event: str
    device: BluetoothDevice

    def __post_init__(self) -> None:
        object.__setattr__(self, "event", _text(self.event, "event"))
        if not isinstance(self.device, BluetoothDevice):
            raise ContractError("bluetooth device must be a BluetoothDevice")

    @property
    def type(self) -> str:
        return "bluetooth.session.event"

    def to_json_value(self) -> dict[str, object]:
        return {"event": self.event, "device": self.device.to_json_value()}
