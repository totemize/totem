"""Selected-child worker for the process-host tracer."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import socket
from typing import Any, Dict, Mapping

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
    parser.add_argument("--bootstrap-json", required=True)
    args = parser.parse_args()
    module_name, separator, factory_name = args.entry_point.partition(":")
    if not separator or not module_name or not factory_name:
        return 2
    try:
        bootstrap = json.loads(args.bootstrap_json)
    except (TypeError, ValueError):
        return 2
    if not isinstance(bootstrap, Mapping):
        return 2
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    try:
        provider = factory(bootstrap)
    except TypeError:
        # API-major-one plugins may still expose the original nullary factory;
        # their manifest remains authoritative, while new providers consume the
        # explicit selected-binding bootstrap above.
        if inspect.signature(factory).parameters:
            raise
        provider = factory()
    # Factory success alone does not mean a selected backend is usable.  The
    # child validates it before sending host.ready so failed radios/storage
    # bindings become failed lifecycle entries rather than false readiness.
    validator = getattr(provider, "validate_startup", None)
    if callable(validator):
        validator()
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
    """Invoke the provider-owned versioned SPI after generic validation.

    This worker intentionally knows no capability family, provider model, or
    action spelling.  Independently released providers extend the runtime by
    implementing ``dispatch(message, attachments, context)``.
    """

    request_id = message.get("id")
    if not isinstance(request_id, str) or not request_id:
        return _result(message, ok=False, error={"code": "invalid_request"})
    dispatch = getattr(provider, "dispatch", None)
    if not callable(dispatch):
        return _result(message, ok=False, error={"code": "unknown_type"})
    try:
        response = dispatch(
            dict(message), dict(message.get("_attachments", {})),
            {"binding_id": message.get("binding_id")},
        )
    except (TypeError, ValueError, AttributeError):
        return _result(message, ok=False, error={"code": "invalid_request"})
    if not isinstance(response, Mapping):
        return _result(message, ok=False, error={"code": "invalid_request"})
    return _result(message, **dict(response))


if __name__ == "__main__":
    raise SystemExit(main())
