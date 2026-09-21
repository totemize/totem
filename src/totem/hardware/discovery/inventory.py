"""Immutable inventory seams that collect evidence without identifying products."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from .facts import HardwareComponent, HardwareFacts
from .profiles import DeviceProfile


@dataclass(frozen=True)
class Inventory:
    """Observed components plus optional data-only profile evidence."""

    facts: HardwareFacts
    profiles: Tuple[DeviceProfile, ...] = ()

    def __post_init__(self) -> None:
        profiles = tuple(sorted(self.profiles, key=lambda item: item.profile_id))
        if len({item.profile_id for item in profiles}) != len(profiles):
            raise ValueError("inventory profile IDs must be unique")
        object.__setattr__(self, "profiles", profiles)

    @classmethod
    def from_components(
        cls, components: Sequence[HardwareComponent], profiles: Sequence[DeviceProfile] = ()
    ) -> "Inventory":
        return cls(facts=HardwareFacts.from_components(components), profiles=tuple(profiles))
