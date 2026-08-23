"""Synthetic provider code that proves catalog inspection does not import providers."""

from __future__ import annotations

import os

from totem_driver_api.capabilities.display import FrameSinkRequest


os.environ["TOTEM_DRIVER_FIXTURE_IMPORTED"] = "1"


class SyntheticDisplayProvider:
    """A no-I/O provider used only after a host deliberately imports it."""

    def write_frame(self, request: FrameSinkRequest) -> dict[str, object]:
        return {"attachment_id": request.attachment_id, "accepted": True}


def create_provider() -> SyntheticDisplayProvider:
    return SyntheticDisplayProvider()
