"""Resolve data-only manifests against normalized evidence before provider import."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from totem_driver_api import CapabilityId

from totem.hardware.catalog.metadata import CatalogRecord, CatalogSnapshot
from totem.hardware.runtime.bindings import BindingPlan, BindingRecord
from totem.hardware.runtime.config import ConfigValidationError, RuntimeConfig

from .facts import HardwareFacts
from .profiles import DeviceProfile


class ResolutionStatus(Enum):
    """Public result states for deterministic binding selection."""

    RESOLVED = "resolved"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class ResolutionError(RuntimeError):
    """A caller attempted to use an unresolved binding."""


@dataclass(frozen=True)
class MatchResult:
    """Complete acceptance or rejection evidence for one provider."""

    record: CatalogRecord
    accepted: bool
    score: int
    supporting: Tuple[str, ...]
    missing: Tuple[str, ...]
    rejected: Tuple[str, ...]

    @property
    def provider_id(self) -> str:
        return self.record.provider_id

    def to_json_value(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "distribution": self.record.distribution_name,
            "missing": list(self.missing),
            "provider_id": self.record.provider_id,
            "rejected": list(self.rejected),
            "score": self.score,
            "supporting": list(self.supporting),
        }


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    binding: Optional[BindingRecord]
    evidence: Tuple[str, ...]
    plan: BindingPlan

    def require_binding(self) -> BindingRecord:
        if self.binding is None:
            raise ResolutionError("; ".join(self.evidence))
        return self.binding


class Resolver:
    """Choose one valid provider from import-free metadata and observed facts."""

    def resolve(
        self,
        catalog: CatalogSnapshot,
        *,
        facts: HardwareFacts,
        capability_id: str,
        profile: Optional[DeviceProfile] = None,
        config: Optional[RuntimeConfig] = None,
        binding_id: Optional[str] = None,
    ) -> ResolutionResult:
        capability = CapabilityId.parse(capability_id)
        declaring = tuple(
            sorted(
                (record for record in catalog.records if capability in record.manifest.capabilities),
                key=lambda record: (record.provider_id, record.distribution_name, record.entry_point_name),
            )
        )
        explicit_provider = self._explicit_provider(config, binding_id)
        candidates = tuple(
            self._match(
                record,
                facts=facts,
                profile=profile,
                config=config,
                binding_id=binding_id,
                explicit=record.provider_id == explicit_provider,
            )
            for record in declaring
            if explicit_provider is None or record.provider_id == explicit_provider
        )
        plan = BindingPlan(
            capability_id=capability.identifier,
            candidates=candidates,
            selected_binding=None,
            explicit_binding_id=binding_id if explicit_provider is not None else None,
        )
        if not declaring:
            return ResolutionResult(
                status=ResolutionStatus.UNAVAILABLE,
                binding=None,
                evidence=("no catalog record declares {}".format(capability.identifier),),
                plan=plan,
            )
        if explicit_provider is not None and not candidates:
            return ResolutionResult(
                status=ResolutionStatus.UNAVAILABLE,
                binding=None,
                evidence=("explicit provider {} does not declare {}".format(explicit_provider, capability.identifier),),
                plan=plan,
            )
        accepted = tuple(item for item in candidates if item.accepted)
        selected = None
        if explicit_provider is not None:
            selected = accepted[0] if accepted else None
        elif accepted:
            highest_score = max(item.score for item in accepted)
            leaders = tuple(item for item in accepted if item.score == highest_score)
            if len(leaders) == 1:
                selected = leaders[0]
            else:
                return ResolutionResult(
                    status=ResolutionStatus.AMBIGUOUS,
                    binding=None,
                    evidence=tuple(item.provider_id for item in leaders),
                    plan=plan,
                )
        if selected is None:
            return ResolutionResult(
                status=ResolutionStatus.UNAVAILABLE,
                binding=None,
                evidence=("no catalog record matches facts for {}".format(capability.identifier),),
                plan=plan,
            )
        binding = self._binding_for(selected.record, capability.identifier, config, binding_id)
        selected_plan = BindingPlan(
            capability_id=capability.identifier,
            candidates=candidates,
            selected_binding=binding,
            explicit_binding_id=binding_id if explicit_provider is not None else None,
        )
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            binding=binding,
            evidence=(),
            plan=selected_plan,
        )

    @staticmethod
    def _explicit_provider(config: Optional[RuntimeConfig], binding_id: Optional[str]) -> Optional[str]:
        if config is None or binding_id is None:
            return None
        binding = next((item for item in config.bindings if item.binding_id == binding_id), None)
        return binding.plugin_id if binding is not None else None

    def _match(
        self,
        record: CatalogRecord,
        *,
        facts: HardwareFacts,
        profile: Optional[DeviceProfile],
        config: Optional[RuntimeConfig],
        binding_id: Optional[str],
        explicit: bool,
    ) -> MatchResult:
        supporting = []
        missing = []
        rejected = []
        score = 0
        manifest = record.manifest
        if explicit:
            supporting.append("explicit:provider={}".format(record.provider_id))
        else:
            profile_values = dict(profile.fact_items()) if profile is not None else {}
            for predicate in manifest.predicates:
                fact = predicate.fact.strip().casefold()
                expected = predicate.equals.strip().casefold()
                observed = facts.value_for(fact)
                if observed == expected:
                    supporting.append("fact:{}={}".format(fact, expected))
                    score += 100
                elif profile_values.get(fact) == expected:
                    supporting.append("profile:{}={}".format(fact, expected))
                    score += 10
                else:
                    missing.append("{}={}".format(fact, expected))
        for prerequisite in manifest.prerequisites:
            key = "service.{}".format(prerequisite.strip().casefold())
            if facts.value_for(key) == "present":
                supporting.append("{}=present".format(key))
                score += 20
            else:
                missing.append("{}=present".format(key))
        for claim in manifest.resources:
            resource = "resource.{}={}".format(claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            if facts.supports(claim):
                supporting.append(resource)
                score += 20
            else:
                missing.append(resource)
        if config is not None:
            try:
                config.effective_settings(manifest, binding_id or self._default_binding_id(record))
            except ConfigValidationError as exc:
                rejected.append("config:{}".format(exc.diagnostic.code))
        return MatchResult(
            record=record,
            accepted=not missing and not rejected,
            score=score,
            supporting=tuple(sorted(supporting)),
            missing=tuple(sorted(missing)),
            rejected=tuple(sorted(rejected)),
        )

    def _binding_for(
        self,
        record: CatalogRecord,
        capability_id: str,
        config: Optional[RuntimeConfig],
        binding_id: Optional[str],
    ) -> BindingRecord:
        resolved_binding_id = binding_id or self._default_binding_id(record, capability_id)
        settings = ()
        if config is not None:
            settings = tuple(sorted(config.effective_settings(record.manifest, resolved_binding_id).to_json_value().items()))
        claims = tuple(
            sorted(record.manifest.resources, key=lambda claim: (claim.kind.casefold(), claim.identifier.casefold()))
        )
        return BindingRecord(
            capability_id=capability_id,
            binding_id=resolved_binding_id,
            provider_record=record,
            claims=claims,
            config=settings,
        )

    @staticmethod
    def _default_binding_id(record: CatalogRecord, capability_id: str = "") -> str:
        return "{}:{}".format(record.provider_id, capability_id or record.manifest.capabilities[0].identifier)
