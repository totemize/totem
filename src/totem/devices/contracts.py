"""Compatibility lifecycle names backed by the public driver API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol

from totem_driver_api.lifecycle import BindingState


# Historical imports retain this name, but the state vocabulary now belongs to
# the public, explicit binding lifecycle.  A device object no longer infers
# readiness, mock status, or ownership from private attributes.
DriverState = BindingState


@dataclass(frozen=True)
class DriverHealth:
    """Legacy-shaped projection of an explicit binding lifecycle state."""

    state: BindingState
    message: Optional[str] = None
    details: Mapping[str, object] = field(default_factory=dict)

    @property
    def operational(self) -> bool:
        return self.state in (BindingState.READY, BindingState.DEGRADED)


class DeviceDriver(Protocol):
    """Marker for historical driver-interface imports.

    Concrete providers are selected and owned only by the canonical runtime.
    Capability-specific protocols retain their own operation signatures; this
    marker deliberately provides no lifecycle implementation or attribute
    inference.
    """
