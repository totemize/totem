"""Public contract for read-only power telemetry."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Optional

from ..identifiers import CapabilityId, ContractError


POWER_TELEMETRY = CapabilityId("power.telemetry", 1)


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError("power {} must be a finite number".format(field))
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ContractError("power {} must be a finite number".format(field))
    return numeric


@dataclass(frozen=True)
class PowerTelemetryRequest:
    """A typed request for the current read-only power snapshot."""

    def to_json_value(self) -> dict[str, object]:
        return {}


@dataclass(frozen=True)
class PowerTelemetrySnapshot:
    """Validated public battery, voltage, charging, and current telemetry."""

    model: str
    battery_percent: float
    voltage_volts: float
    current_amps: float
    power_plugged: Optional[bool] = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ContractError("power model must be non-empty")
        battery_percent = _finite_number(self.battery_percent, "battery_percent")
        if not 0.0 <= battery_percent <= 100.0:
            raise ContractError("power battery_percent must be between 0 and 100")
        object.__setattr__(self, "battery_percent", battery_percent)
        object.__setattr__(self, "voltage_volts", _finite_number(self.voltage_volts, "voltage_volts"))
        object.__setattr__(self, "current_amps", _finite_number(self.current_amps, "current_amps"))
        if self.power_plugged is not None and not isinstance(self.power_plugged, bool):
            raise ContractError("power power_plugged must be boolean or null")

    def to_json_value(self) -> dict[str, object]:
        return {
            "model": self.model,
            "battery_percent": self.battery_percent,
            "voltage_volts": self.voltage_volts,
            "current_amps": self.current_amps,
            "power_plugged": self.power_plugged,
        }

    def to_push(self) -> "PowerTelemetryPush":
        return PowerTelemetryPush(self)


@dataclass(frozen=True)
class PowerTelemetryPush:
    """Typed event-shaped representation of a validated power snapshot."""

    telemetry: PowerTelemetrySnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.telemetry, PowerTelemetrySnapshot):
            raise ContractError("power telemetry push requires a snapshot")

    def to_json_value(self) -> dict[str, object]:
        return {"type": "power.telemetry.push", "telemetry": self.telemetry.to_json_value()}

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))
