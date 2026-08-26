"""Child-only concrete power telemetry implementations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerDriverHealth:
    """Legacy-shaped local lifecycle observation without legacy ownership."""

    state: str
    initialized: bool
    is_mock: bool = False

    @property
    def operational(self) -> bool:
        return self.state in ("ready", "mock")
