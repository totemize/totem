"""Public contract for a display frame sink capability."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..identifiers import CapabilityId, ContractError


FRAME_SINK = CapabilityId("display.frame-sink", 1)


@dataclass(frozen=True)
class FrameSinkRequest:
    """JSON metadata for a raw frame attachment owned by the carrier."""

    attachment_id: str
    width: int
    height: int
    pixel_format: str

    def __post_init__(self) -> None:
        if not self.attachment_id:
            raise ContractError("frame attachment_id must be non-empty")
        if isinstance(self.width, bool) or self.width < 1:
            raise ContractError("frame width must be positive")
        if isinstance(self.height, bool) or self.height < 1:
            raise ContractError("frame height must be positive")
        if not self.pixel_format:
            raise ContractError("frame pixel_format must be non-empty")

    def to_json_value(self) -> dict[str, object]:
        return {
            "attachment_id": self.attachment_id,
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_json_value(), sort_keys=True, separators=(",", ":"))
