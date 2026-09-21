"""Resolved binding records passed from selection into runtime ownership."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Tuple

from totem_driver_api import ResourceClaim

from totem.hardware.catalog.metadata import CatalogRecord


@dataclass(frozen=True)
class BindingRecord:
    """A provider-independent plan for one stable capability binding."""

    capability_id: str
    binding_id: str
    provider_record: CatalogRecord
    claims: Tuple[ResourceClaim, ...]
    config: Tuple[Tuple[str, object], ...]


@dataclass(frozen=True)
class BindingPlan:
    """A complete, metadata-only decision before host or broker work."""

    capability_id: str
    candidates: Tuple[Any, ...]
    selected_binding: BindingRecord | None
    explicit_binding_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "capability_id": self.capability_id,
                "candidates": [candidate.to_json_value() for candidate in self.candidates],
                "explicit_binding_id": self.explicit_binding_id,
                "selected_binding_id": self.selected_binding.binding_id if self.selected_binding else None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
