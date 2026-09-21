"""Stable lifecycle vocabulary shared by drivers and the hardware runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional


class BindingState(str, Enum):
    """Explicit lifecycle states for one resolved capability binding."""

    DISCOVERED = "discovered"
    MATCHED = "matched"
    BOUND = "bound"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    FAILED = "failed"
    RETRYING = "retrying"
    QUARANTINED = "quarantined"
    CONTAMINATED = "contaminated"
    CLOSED = "closed"


class HealthState(str, Enum):
    """Operator-facing aggregate health without provider implementation detail."""

    READY = "ready"
    DEGRADED = "degraded"
    FAILED = "failed"
    CLOSED = "closed"


def _freeze_details(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class LifecycleEvent:
    """An immutable, ordered, redacted lifecycle change notification."""

    sequence: int
    binding_id: str
    previous: Optional[BindingState]
    state: BindingState
    code: Optional[str] = None
    details: Mapping[str, object] = field(default_factory=dict)
    snapshot: object = None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("lifecycle event sequence must be positive")
        if not self.binding_id:
            raise ValueError("lifecycle event binding id is required")
        object.__setattr__(self, "details", _freeze_details(self.details))
