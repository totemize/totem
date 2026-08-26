"""Data-only provider support types for declared radio services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RadioService(Enum):
    NETWORK_MANAGER = ("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
    BLUEZ = ("org.bluez", "/org/bluez")

    @property
    def destination(self) -> str:
        return self.value[0]

    @property
    def root_path(self) -> str:
        return self.value[1]


@dataclass(frozen=True)
class RadioState:
    available: bool
    enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.available, bool) or not isinstance(self.enabled, bool):
            raise ValueError("radio state values must be boolean")

    def to_json_value(self) -> dict[str, bool]:
        return {"available": self.available, "enabled": self.enabled}
