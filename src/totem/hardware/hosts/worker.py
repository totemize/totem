"""Selected-child worker for the process-host tracer."""

from __future__ import annotations

import argparse
import importlib
import os
import socket
from typing import Any, Dict

from totem_driver_api.capabilities.display import FrameSinkRequest

from .protocol import ProtocolError, receive_frame, send_frame


def _result(message: Dict[str, Any], *, ok: bool, **values: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "type": "{}.result".format(message.get("type", "host.error")),
        "id": message.get("id"),
        "ok": ok,
    }
    result.update(values)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--binding-id", required=True)
    parser.add_argument("--entry-point", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    module_name, separator, factory_name = args.entry_point.partition(":")
    if not separator or not module_name or not factory_name:
        return 2
    module = importlib.import_module(module_name)
    provider = getattr(module, factory_name)()
    carrier = socket.socket(fileno=args.fd)
    send_frame(
        carrier,
        {
            "type": "host.ready",
            "binding_id": args.binding_id,
            "session_id": args.session_id,
        },
    )
    while True:
        try:
            message = receive_frame(carrier)
        except (OSError, ProtocolError):
            return 0
        result = _dispatch(provider, message)
        result["binding_id"] = args.binding_id
        result["session_id"] = args.session_id
        send_frame(carrier, result)


def _dispatch(provider: Any, message: Dict[str, Any]) -> Dict[str, Any]:
    request_id = message.get("id")
    if not isinstance(request_id, str) or not request_id:
        return _result(message, ok=False, error={"code": "invalid_request"})
    if message.get("type") != "display.frame.write":
        return _result(message, ok=False, error={"code": "unknown_type"})
    frame = message.get("frame")
    attachments = message.get("_attachments")
    if not isinstance(frame, dict) or not isinstance(attachments, dict):
        return _result(message, ok=False, error={"code": "invalid_request"})
    try:
        request = FrameSinkRequest(
            attachment_id=frame["attachment_id"],
            width=frame["width"],
            height=frame["height"],
            pixel_format=frame["pixel_format"],
        )
        attachment = attachments.get(request.attachment_id)
        if not isinstance(attachment, bytes):
            raise ValueError("missing attachment")
        provider_result = provider.write_frame(request)
    except (KeyError, ValueError, TypeError):
        return _result(message, ok=False, error={"code": "invalid_request"})
    return _result(
        message,
        ok=True,
        attachment_id=provider_result["attachment_id"],
        accepted=provider_result["accepted"],
        provider_imported=os.environ.get("TOTEM_DRIVER_FIXTURE_IMPORTED") == "1",
    )


if __name__ == "__main__":
    raise SystemExit(main())
