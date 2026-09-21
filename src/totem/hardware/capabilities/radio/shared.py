"""Generic radio resource claims and deterministic coexistence policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from totem_driver_api import ResourceClaim


_MODES = frozenset({"wifi.station", "wifi.hotspot", "bluetooth.scan", "bluetooth.advertise"})
_PERMITTED_PAIRS = frozenset(
    {
        frozenset(("wifi.station", "wifi.station")),
        frozenset(("wifi.station", "bluetooth.scan")),
        frozenset(("wifi.station", "bluetooth.advertise")),
        frozenset(("bluetooth.scan", "bluetooth.scan")),
        frozenset(("bluetooth.scan", "bluetooth.advertise")),
        frozenset(("bluetooth.advertise", "bluetooth.advertise")),
        frozenset(("wifi.hotspot", "wifi.hotspot")),
    }
)


class RadioCompatibilityError(RuntimeError):
    """Two claimed radio modes cannot safely share a physical radio."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("radio {} must be a non-empty string".format(field))
    return value.strip().casefold()


@dataclass(frozen=True)
class RadioConstraint:
    """One provider's generic radio-resource and operation-mode declaration."""

    phy: str
    interface: str
    adapter: str
    mode: str
    compatibility_group: str

    def __post_init__(self) -> None:
        for field in ("phy", "interface", "adapter", "mode", "compatibility_group"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if self.mode not in _MODES:
            raise ValueError("radio mode is not declared: {}".format(self.mode))

    def claims(self) -> Tuple[ResourceClaim, ...]:
        """Translate only into standard broker claims; no provider calls occur."""

        return (
            ResourceClaim("phy", self.phy, exclusive=False, group=self.compatibility_group),
            ResourceClaim("interface", self.interface, exclusive=False, group=self.compatibility_group),
            ResourceClaim("adapter", self.adapter, exclusive=False, group=self.compatibility_group),
            ResourceClaim("compatibility", self.mode, exclusive=False, group=self.compatibility_group),
        )

    @classmethod
    def from_claims(cls, claims: Iterable[ResourceClaim]) -> Optional["RadioConstraint"]:
        values: dict[str, str] = {}
        group: Optional[str] = None
        for claim in claims:
            kind = claim.kind.strip().casefold()
            if kind not in {"phy", "interface", "adapter", "compatibility"}:
                continue
            values[kind] = claim.identifier
            if kind == "compatibility":
                group = claim.group
        if "compatibility" not in values:
            return None
        if group is None:
            raise ValueError("radio compatibility claim must name a compatibility group")
        missing = sorted({"phy", "interface", "adapter", "compatibility"}.difference(values))
        if missing:
            raise ValueError("radio constraint is missing {} claim".format(", ".join(missing)))
        return cls(values["phy"], values["interface"], values["adapter"], values["compatibility"], group)


class RadioCompatibilityPolicy:
    """Pure explicit matrix for radio claims sharing one PHY and group."""

    def permits(self, left: RadioConstraint, right: RadioConstraint) -> bool:
        if left.compatibility_group != right.compatibility_group or left.phy != right.phy:
            return True
        return frozenset((left.mode, right.mode)) in _PERMITTED_PAIRS

    def validate(self, bindings: Iterable[object]) -> None:
        constraints = []
        for binding in bindings:
            constraint = RadioConstraint.from_claims(getattr(binding, "claims"))
            if constraint is not None:
                constraints.append((getattr(binding, "binding_id"), constraint))
        for index, (left_id, left) in enumerate(constraints):
            for right_id, right in constraints[index + 1 :]:
                if not self.permits(left, right):
                    raise RadioCompatibilityError(
                        "radio modes {} and {} cannot coexist on {} in {} ({} vs {})".format(
                            left.mode,
                            right.mode,
                            left.phy,
                            left.compatibility_group,
                            left_id,
                            right_id,
                        )
                    )
