"""Data-only optional profiles; profiles never import or instantiate providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from .facts import HardwareComponent


@dataclass(frozen=True)
class DeviceProfile:
    """Named supplemental component evidence for a known installation."""

    profile_id: str
    components: Tuple[HardwareComponent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile ID must be a non-empty string")
        profile_id = self.profile_id.strip().casefold()
        components = tuple(sorted(self.components, key=lambda item: item.sort_key))
        if len(set(components)) != len(components):
            raise ValueError("profile components must be unique")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "components", components)

    @classmethod
    def from_mapping(cls, profile_id: str, value: Mapping[str, object]) -> "DeviceProfile":
        if not isinstance(value, Mapping) or set(value).difference({"components"}):
            raise ValueError("profile must contain only components")
        raw_components = value.get("components", ())
        if not isinstance(raw_components, Sequence) or isinstance(raw_components, (str, bytes)):
            raise ValueError("profile components must be a sequence")
        components = []
        for raw_component in raw_components:
            if not isinstance(raw_component, Mapping) or set(raw_component).difference(
                {"kind", "identifier", "evidence"}
            ):
                raise ValueError("profile component must contain kind, identifier, and evidence")
            kind = raw_component.get("kind")
            identifier = raw_component.get("identifier")
            evidence = raw_component.get("evidence", {})
            if not isinstance(kind, str) or not isinstance(identifier, str) or not isinstance(evidence, Mapping):
                raise ValueError("profile component fields are invalid")
            components.append(HardwareComponent(kind, identifier, evidence))
        return cls(profile_id=profile_id, components=tuple(components))

    def fact_items(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(item for component in self.components for item in component.fact_items())
