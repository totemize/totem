"""Normalized, immutable observed hardware evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from totem_driver_api import ResourceClaim


@dataclass(frozen=True)
class HardwareFacts:
    """Exact synthetic facts used by the first catalog-to-claim tracer."""

    values: Tuple[Tuple[str, str], ...]

    def __post_init__(self) -> None:
        if tuple(sorted(self.values)) != self.values:
            raise ValueError("hardware facts must be sorted")
        if len({key for key, _value in self.values}) != len(self.values):
            raise ValueError("hardware fact keys must be unique")

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "HardwareFacts":
        normalized = []
        for key, value in values.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("hardware fact keys must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("hardware fact values must be non-empty strings")
            normalized.append((key.strip(), value.strip()))
        return cls(values=tuple(sorted(normalized)))

    def value_for(self, key: str) -> Optional[str]:
        for fact_key, value in self.values:
            if fact_key == key:
                return value
        return None

    def supports(self, claim: ResourceClaim) -> bool:
        """Match a manifest claim only to the exact declared resource fact."""

        return self.value_for("resource.{}".format(claim.kind)) == claim.identifier

