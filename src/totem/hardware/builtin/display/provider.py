"""Variant-neutral, child-only provider for the built-in display family.

Selection remains data-only until the runtime has resolved the manifest and
granted its declared leases.  Concrete panel modules are intentionally not
imported here: their migrations live in later, independently reviewable
changes.
"""

from __future__ import annotations

from typing import Iterable, Optional, Protocol, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.display import FrameSinkRequest


_SUPPORTED_2IN13_VARIANTS = frozenset(
    {
        "waveshare-2in13",
        "waveshare-2in13-pi5",
        "waveshare-2in13-pi5-sw-cs",
        "waveshare-2in13-v1",
        "waveshare-2in13-v2",
        "waveshare-2in13-v3",
        "waveshare-2in13-v4",
    }
)
_REQUIRED_CLAIMS = frozenset(
    {
        ("gpio", "bcm:17,18,24,25"),
        ("spi", "spi0.0"),
    }
)
_FRAME_WIDTH = 250
_FRAME_HEIGHT = 122
_PIXEL_FORMAT = "mono1"


class DisplaySelectionError(ValueError):
    """Selection or input failed before a display transport receives I/O."""


class FrameTransport(Protocol):
    """The narrow, injected physical transport used only in the child."""

    def write_frame(self, request: FrameSinkRequest) -> None:
        """Submit one already-validated frame descriptor."""


class DisplayProvider:
    """Validate a selected 2.13 panel frame before touching its transport.

    A process-host factory intentionally starts unconfigured.  Runtime
    composition supplies the resolved panel variant, claimed resources, and a
    concrete child transport after the manifest-first resolution path.  This
    keeps profile data and hardware imports outside daemon selection.
    """

    def __init__(
        self,
        *,
        variant: Optional[str] = None,
        claims: Iterable[ResourceClaim] = (),
        transport: Optional[FrameTransport] = None,
    ) -> None:
        self._variant = variant.strip().casefold() if isinstance(variant, str) else None
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._transport = transport

    def write_frame(self, request: FrameSinkRequest) -> dict[str, object]:
        """Validate panel selection and frame shape before transport I/O."""

        self._require_selected_claimed_transport()
        if request.width != _FRAME_WIDTH or request.height != _FRAME_HEIGHT:
            raise ValueError("display frame dimensions do not match selected panel")
        if request.pixel_format != _PIXEL_FORMAT:
            raise ValueError("display frame pixel format is unsupported")
        assert self._transport is not None  # checked by the guard above
        self._transport.write_frame(request)
        return {"attachment_id": request.attachment_id, "accepted": True}

    def _require_selected_claimed_transport(self) -> None:
        if self._variant not in _SUPPORTED_2IN13_VARIANTS:
            raise DisplaySelectionError("display variant is not declared")
        declared_claims = frozenset(
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold())
            for claim in self._claims
        )
        if not _REQUIRED_CLAIMS.issubset(declared_claims):
            raise DisplaySelectionError("display SPI/GPIO claims are incomplete")
        if self._transport is None:
            raise DisplaySelectionError("display transport is unavailable until child composition")


def create_provider() -> DisplayProvider:
    """Return a side-effect-free child factory product.

    The worker imports this function only after catalog resolution and broker
    acquisition.  It neither probes nor opens SPI/GPIO; composition injects
    the selected variant and leased transport before requests are accepted.
    """

    return DisplayProvider()
