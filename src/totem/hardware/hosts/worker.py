"""Selected-child worker for the process-host tracer."""

from __future__ import annotations

import argparse
import importlib
import os
import socket
from typing import Any, Dict

from totem_driver_api.capabilities.display import FrameSinkRequest
from totem_driver_api.capabilities.nfc import NfcWriteRequest
from totem_driver_api.capabilities.power import PowerTelemetryRequest
from totem_driver_api.capabilities.radio.wifi import WifiConnectRequest, WifiHotspotRequest
from totem_driver_api.capabilities.storage import StoragePath, StorageWriteRequest

from .protocol import ProtocolError, receive_frame, send_frame


_PUBLIC_ERROR_MESSAGES = {
    "invalid_request": "invalid request",
    "unknown_type": "unknown message type",
}


def _result(message: Dict[str, Any], *, ok: bool, **values: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "type": "{}.result".format(message.get("type", "host.error")),
        "id": message.get("id"),
        "ok": ok,
    }
    error = values.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str) and "message" not in error:
        values["error"] = {
            "code": error["code"],
            "message": _PUBLIC_ERROR_MESSAGES.get(error["code"], "request failed"),
        }
    result.update(values)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--binding-id", required=True, action="append")
    parser.add_argument("--entry-point", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--generation", type=int, required=True)
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
            "binding_ids": args.binding_id,
            "session_id": args.session_id,
            "generation": args.generation,
        },
    )
    while True:
        try:
            message = receive_frame(carrier)
        except (OSError, ProtocolError):
            return 0
        binding_id = message.get("binding_id")
        if binding_id not in args.binding_id:
            result = _result(message, ok=False, error={"code": "invalid_request"})
            binding_id = ""
        else:
            result = _dispatch(provider, message)
        result["binding_id"] = binding_id
        result["session_id"] = args.session_id
        result["generation"] = args.generation
        send_frame(carrier, result)


def _dispatch(provider: Any, message: Dict[str, Any]) -> Dict[str, Any]:
    request_id = message.get("id")
    if not isinstance(request_id, str) or not request_id:
        return _result(message, ok=False, error={"code": "invalid_request"})
    message_type = message.get("type")
    if message_type in ("power.telemetry.read", "power.telemetry.push"):
        try:
            PowerTelemetryRequest()
            if message_type == "power.telemetry.read":
                telemetry = provider.snapshot().to_json_value()
            else:
                telemetry = provider.telemetry_push().to_json_value()
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
        return _result(message, ok=True, telemetry=telemetry)
    if message_type == "nfc.tag.read":
        try:
            return _result(message, ok=True, tag=provider.read().to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "nfc.tag.write":
        try:
            request = NfcWriteRequest.from_json_value({"data_b64": message.get("data_b64")})
            provider.write(request.data)
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
        return _result(message, ok=True, accepted=True)
    if message_type == "nfc.tag.poll":
        try:
            return _result(message, ok=True, poll=provider.poll().to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "storage.files.read":
        try:
            request = StoragePath(message.get("path"))
            return _result(message, ok=True, file=provider.read(request.value).to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "storage.files.write":
        try:
            request = StorageWriteRequest.from_json_value(
                {"path": message.get("path"), "data_b64": message.get("data_b64")}
            )
            provider.write(request.path.value, request.data)
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
        return _result(message, ok=True, accepted=True)
    if message_type == "storage.files.list":
        try:
            request = StoragePath(message.get("path", "."))
            return _result(message, ok=True, files=provider.list(request.value).to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "storage.files.delete":
        try:
            request = StoragePath(message.get("path"))
            return _result(message, ok=True, deletion=provider.delete(request.value).to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "wifi.connection.scan":
        try:
            return _result(message, ok=True, scan=provider.scan().to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "wifi.connection.connect":
        try:
            request = WifiConnectRequest(message.get("ssid"), message.get("password"))
            return _result(message, ok=True, connection=provider.connect(request.ssid, request.password or "").to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "wifi.connection.disconnect":
        try:
            return _result(message, ok=True, disconnect=provider.disconnect().to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type == "wifi.connection.hotspot":
        try:
            request = WifiHotspotRequest(message.get("ssid"))
            return _result(message, ok=True, hotspot=provider.create_hotspot(request.ssid).to_json_value())
        except (AttributeError, TypeError, ValueError):
            return _result(message, ok=False, error={"code": "invalid_request"})
    if message_type != "display.frame.write":
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
