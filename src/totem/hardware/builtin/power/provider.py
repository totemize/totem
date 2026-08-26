"""Child-only provider for validated built-in power telemetry."""

from __future__ import annotations

from typing import Iterable, Optional, Protocol, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.power import PowerTelemetryPush, PowerTelemetrySnapshot


_SUPPORTED_MODELS = {"pisugar2": "0x75", "waveshare_ups_hat_c": "0x43"}
_REQUIRED_CLAIMS = frozenset({("i2c", "1")})


class PowerSelectionError(ValueError):
    """Selection or input failed before a power transport receives I/O."""


class PowerDriver(Protocol):
    """The narrow injected driver contract used after selection and leasing."""

    def get_status(self) -> object:
        """Return the latest legacy-compatible telemetry shape."""


class PowerProvider:
    """Translate an injected concrete UPS driver into the public capability."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        i2c_address: Optional[str] = None,
        claims: Iterable[ResourceClaim] = (),
        driver: Optional[PowerDriver] = None,
    ) -> None:
        self._model = model.strip().casefold() if isinstance(model, str) else None
        self._i2c_address = i2c_address.strip().casefold() if isinstance(i2c_address, str) else None
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._driver = driver

    def snapshot(self) -> PowerTelemetrySnapshot:
        """Validate selection and lease ownership before any UPS access."""

        self._require_selected_claimed_driver()
        assert self._driver is not None
        status = self._driver.get_status()
        try:
            return PowerTelemetrySnapshot(
                model=status.model,
                battery_percent=status.battery_percent,
                voltage_volts=status.voltage_volts,
                current_amps=status.current_amps,
                power_plugged=status.power_plugged,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("power driver returned invalid telemetry") from exc

    def telemetry_push(self) -> PowerTelemetryPush:
        """Return the explicit typed event form of one fresh snapshot."""

        return self.snapshot().to_push()

    def _require_selected_claimed_driver(self) -> None:
        if self._model not in _SUPPORTED_MODELS:
            raise PowerSelectionError("power model is not declared")
        expected_address = _SUPPORTED_MODELS[self._model]
        if self._i2c_address != expected_address:
            raise PowerSelectionError("power I2C address does not match selected model")
        declared_claims = frozenset(
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            for claim in self._claims
        )
        if not _REQUIRED_CLAIMS.issubset(declared_claims):
            raise PowerSelectionError("power I2C claims are incomplete")
        if self._driver is None:
            raise PowerSelectionError("power driver is unavailable until child composition")


def create_provider() -> PowerProvider:
    """Return a side-effect-free factory product after catalog resolution."""

    return PowerProvider()
