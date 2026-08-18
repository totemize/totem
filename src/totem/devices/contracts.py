"""Shared contracts and lifecycle state for Totem device drivers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class DriverState(str, Enum):
    """Lifecycle states reported by every device driver."""

    NEW = "new"
    READY = "ready"
    MOCK = "mock"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass(frozen=True)
class DriverHealth:
    """A serializable snapshot of a driver's current health."""

    state: DriverState
    initialized: bool
    is_mock: bool
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def operational(self) -> bool:
        return self.state in (DriverState.READY, DriverState.MOCK)


class DeviceDriver(ABC):
    """Common lifecycle contract implemented by all concrete drivers.

    Device-specific interfaces add their own operations. ``close`` and
    ``health`` have conservative defaults so existing drivers gain a uniform
    lifecycle without pretending to know how each hardware transport should
    release its private resources.
    """

    IS_MOCK = False

    @abstractmethod
    def init(self):
        """Initialize the driver, returning false only for a known failure."""
        raise NotImplementedError

    @property
    def is_mock(self) -> bool:
        implicit_transport = (
            hasattr(self, "USE_HARDWARE") and not self.USE_HARDWARE
        ) or (
            hasattr(self, "hardware_available")
            and not self.hardware_available
        )
        return bool(
            self.IS_MOCK
            or getattr(self, "mock_mode", False)
            or implicit_transport
        )

    def health(self) -> DriverHealth:
        initialized = bool(getattr(self, "initialized", False))
        closed = bool(getattr(self, "_closed", False))

        if closed:
            state = DriverState.CLOSED
        elif self.is_mock and initialized:
            state = DriverState.MOCK
        elif initialized:
            state = DriverState.READY
        else:
            state = DriverState.NEW

        return DriverHealth(
            state=state,
            initialized=initialized,
            is_mock=self.is_mock,
        )

    def close(self) -> None:
        """Mark the driver closed after device-specific cleanup, if any."""
        if hasattr(self, "initialized"):
            self.initialized = False
        self._closed = True
