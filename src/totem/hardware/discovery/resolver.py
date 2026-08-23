"""Resolve a capability request from import-free metadata and exact facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from totem_driver_api import CapabilityId, ResourceClaim

from totem.hardware.catalog.metadata import CatalogRecord, CatalogSnapshot
from totem.hardware.runtime.bindings import BindingRecord

from .facts import HardwareFacts


class ResolutionStatus(Enum):
    """Public result states for the minimal resolver tracer."""

    RESOLVED = "resolved"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class ResolutionError(RuntimeError):
    """A caller attempted to use an unresolved binding."""


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    binding: BindingRecord | None
    evidence: Tuple[str, ...]

    def require_binding(self) -> BindingRecord:
        if self.binding is None:
            raise ResolutionError("; ".join(self.evidence))
        return self.binding


class Resolver:
    """Choose exactly one manifest candidate before any provider import."""

    def resolve(
        self,
        catalog: CatalogSnapshot,
        *,
        facts: HardwareFacts,
        capability_id: str,
    ) -> ResolutionResult:
        capability = CapabilityId.parse(capability_id)
        declaring = tuple(
            record
            for record in catalog.records
            if capability in record.manifest.capabilities
        )
        if not declaring:
            return ResolutionResult(
                status=ResolutionStatus.UNAVAILABLE,
                binding=None,
                evidence=("no catalog record declares {}".format(capability.identifier),),
            )
        matches = tuple(
            record
            for record in declaring
            if all(facts.supports(claim) for claim in record.manifest.resources)
        )
        if not matches:
            return ResolutionResult(
                status=ResolutionStatus.UNAVAILABLE,
                binding=None,
                evidence=("no catalog record matches facts for {}".format(capability.identifier),),
            )
        if len(matches) > 1:
            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                binding=None,
                evidence=tuple(
                    "{}:{}".format(record.distribution_name, record.provider_id)
                    for record in matches
                ),
            )
        record = matches[0]
        claims = tuple(
            sorted(
                record.manifest.resources,
                key=lambda claim: (claim.kind.lower(), claim.identifier.lower()),
            )
        )
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            binding=BindingRecord(
                capability_id=capability.identifier,
                binding_id="{}:{}".format(record.provider_id, capability.identifier),
                provider_record=record,
                claims=claims,
                config=(),
            ),
            evidence=(),
        )

