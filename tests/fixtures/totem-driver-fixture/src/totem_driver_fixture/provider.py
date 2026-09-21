"""Synthetic provider code that proves catalog inspection does not import providers."""

from __future__ import annotations

import os

from totem_driver_api.capabilities.display import FrameSinkRequest


os.environ["TOTEM_DRIVER_FIXTURE_IMPORTED"] = "1"


class SyntheticDisplayProvider:
    """A no-I/O provider used only after a host deliberately imports it."""

    def __init__(self, bootstrap: object) -> None:
        self.bootstrap = bootstrap

    def dispatch(
        self, message: dict[str, object], attachments: dict[str, object], context: dict[str, object]
    ) -> dict[str, object]:
        frame = message.get("frame")
        if message.get("type") != "display.frame.write" or not isinstance(frame, dict):
            return {"ok": False, "error": {"code": "unknown_type"}}
        attachment_id = frame.get("attachment_id")
        if not isinstance(attachment_id, str) or not isinstance(attachments.get(attachment_id), bytes):
            return {"ok": False, "error": {"code": "invalid_request"}}
        return {
            "ok": True,
            "attachment_id": attachment_id,
            "accepted": True,
            "provider_imported": True,
            "bootstrap_binding_id": context.get("binding_id"),
        }

    def write_frame(self, request: FrameSinkRequest) -> dict[str, object]:
        return {"attachment_id": request.attachment_id, "accepted": True}


def create_provider(bootstrap: object) -> SyntheticDisplayProvider:
    return SyntheticDisplayProvider(bootstrap)
