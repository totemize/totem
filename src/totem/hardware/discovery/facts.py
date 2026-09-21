"""Normalized, immutable observed hardware evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from totem_driver_api import ResourceClaim


def _normalize(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(field))
    return value.strip().casefold()


@dataclass(frozen=True)
class HardwareComponent:
    """One observed component and its normalized, non-executable evidence."""

    kind: str
    identifier: str
    evidence: object = ()

    def __post_init__(self) -> None:
        kind = _normalize(self.kind, "component kind")
        identifier = _normalize(self.identifier, "component identifier")
        raw_evidence = self.evidence
        items = raw_evidence.items() if isinstance(raw_evidence, Mapping) else raw_evidence
        try:
            normalized = tuple(
                sorted(
                    (_normalize(str(key), "evidence key"), _normalize(value, "evidence value"))
                    for key, value in items
                )
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("component evidence must be string pairs") from exc
        if len({key for key, _value in normalized}) != len(normalized):
            raise ValueError("component evidence keys must be unique")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "evidence", normalized)

    @property
    def sort_key(self) -> Tuple[str, str, Tuple[Tuple[str, str], ...]]:
        return (self.kind, self.identifier, self.evidence)  # type: ignore[return-value]

    def fact_items(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(
            ("{}.{}.{}".format(self.kind, self.identifier, key), value)
            for key, value in self.evidence  # type: ignore[union-attr]
        )


@dataclass(frozen=True)
class HardwareFacts:
    """Ordered observed facts, independent of a product model or provider code."""

    values: Tuple[Tuple[str, str], ...]
    components: Tuple[HardwareComponent, ...] = ()

    def __post_init__(self) -> None:
        normalized_values = tuple(
            sorted((_normalize(key, "hardware fact key"), _normalize(value, "hardware fact value")) for key, value in self.values)
        )
        if len({key for key, _value in normalized_values}) != len(normalized_values):
            raise ValueError("hardware fact keys must be unique")
        components = tuple(sorted(self.components, key=lambda item: item.sort_key))
        if len(set(components)) != len(components):
            raise ValueError("hardware components must be unique")
        object.__setattr__(self, "values", normalized_values)
        object.__setattr__(self, "components", components)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "HardwareFacts":
        return cls(values=tuple(values.items()))

    @classmethod
    def from_components(cls, components: Sequence[HardwareComponent]) -> "HardwareFacts":
        frozen_components = tuple(components)
        return cls(
            values=tuple(item for component in frozen_components for item in component.fact_items()),
            components=frozen_components,
        )

    def value_for(self, key: str) -> Optional[str]:
        normalized_key = _normalize(key, "hardware fact key")
        for fact_key, value in self.values:
            if fact_key == normalized_key:
                return value
        return None

    def supports(self, claim: ResourceClaim) -> bool:
        """Match provider resources only to exact observed resource facts."""
        identifier = _normalize(claim.identifier, "resource identifier")
        # The original compact spelling remains accepted for a single
        # resource kind.  The keyed spelling permits a device to report more
        # than one resource of the same kind (for example NetworkManager and
        # BlueZ D-Bus names) without a lossy model-specific branch.
        return (
            self.value_for("resource.{}".format(claim.kind)) == identifier
            or self.value_for("resource.{}.{}".format(claim.kind, identifier)) == "present"
        )
