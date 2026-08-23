"""Resolved binding records passed from selection into runtime ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from totem_driver_api import ResourceClaim

from totem.hardware.catalog.metadata import CatalogRecord


@dataclass(frozen=True)
class BindingRecord:
    """A provider-independent plan for one stable capability binding."""

    capability_id: str
    binding_id: str
    provider_record: CatalogRecord
    claims: Tuple[ResourceClaim, ...]
    config: Tuple[Tuple[str, str], ...]

