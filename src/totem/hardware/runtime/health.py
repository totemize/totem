"""Redacted typed health projections for the application-facing runtime."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from totem_driver_api.lifecycle import HealthState

from .lifecycle import BindingSnapshot, RuntimeSnapshot


@dataclass(frozen=True)
class RuntimeBindingHealth:
    """Safe health for one opaque binding; no config, token, or driver leaks."""

    binding_id: str
    capability_id: str
    required: bool
    state: str
    generation: int
    quarantined: bool
    contaminated: bool


@dataclass(frozen=True)
class RuntimeHealth:
    """Immutable runtime readiness and redacted binding health projection."""

    ready: bool
    degraded: bool
    closed: bool
    state: HealthState
    bindings: Mapping[str, RuntimeBindingHealth]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bindings", MappingProxyType(dict(self.bindings)))

    @classmethod
    def from_snapshot(
        cls,
        snapshot: RuntimeSnapshot,
        capability_ids: Mapping[str, str],
    ) -> "RuntimeHealth":
        bindings = {
            binding_id: cls._binding_health(binding, capability_ids[binding_id])
            for binding_id, binding in snapshot.bindings.items()
        }
        return cls(
            ready=snapshot.ready,
            degraded=snapshot.health is HealthState.DEGRADED,
            closed=snapshot.closed,
            state=snapshot.health,
            bindings=bindings,
        )

    @staticmethod
    def _binding_health(snapshot: BindingSnapshot, capability_id: str) -> RuntimeBindingHealth:
        return RuntimeBindingHealth(
            binding_id=snapshot.binding_id,
            capability_id=capability_id,
            required=snapshot.required,
            state=snapshot.state.value,
            generation=snapshot.generation,
            quarantined=snapshot.quarantined,
            contaminated=snapshot.contaminated,
        )
