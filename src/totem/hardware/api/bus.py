"""Generic capability-handle dispatch for canonical hardware bus messages."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from totem.hardware.capabilities.base import CapabilityUnavailable
from totem.hardware.capabilities.display import DisplayHandle
from totem.hardware.hosts.process import HostError
from totem.hardware.hosts.protocol import MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS


_MESSAGE_CAPABILITIES = {"display.frame.write": "display.frame-sink@1"}


def _error(message: Mapping[str, Any], code: str) -> Dict[str, Any]:
    message_type = message.get("type")
    return {
        "type": "{}.result".format(message_type if isinstance(message_type, str) else "error"),
        "id": message.get("id"),
        "ok": False,
        "error": {"code": code, "message": _public_error_message(code)},
    }


def _public_error_message(code: str) -> str:
    return {
        "invalid_request": "invalid request",
        "unknown_type": "unknown message type",
        "binding_unavailable": "binding unavailable",
        "host_unavailable": "host unavailable",
        "attachment_too_large": "attachment payload exceeds runtime bound",
        "invalid_attachments": "attachments are invalid",
    }.get(code, "request failed")


class HardwareBus:
    """Route NIP-5D-shaped requests through opaque capability handles only.

    ``HardwareRuntime`` is the canonical source of handles.  The mapping form
    remains a narrow migration seam for the prior process-host tracer; it
    stores handles, never providers or driver objects.
    """

    def __init__(self, runtime_or_bindings: object) -> None:
        self._runtime = runtime_or_bindings if hasattr(runtime_or_bindings, "handle") else None
        self._bindings: Dict[str, DisplayHandle] = (
            {} if self._runtime is not None else dict(runtime_or_bindings)  # type: ignore[arg-type]
        )

    @property
    def runtime(self) -> Optional[object]:
        """Return the injected sole runtime when this is the canonical path."""

        return self._runtime

    def dispatch(self, message: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        """Return one stable correlated result, or ignore an unsolicited push."""

        if not isinstance(message, Mapping):
            return _error({}, "invalid_request")
        request_id = message.get("id")
        if not isinstance(request_id, str) or not request_id:
            return None
        message_type = message.get("type")
        capability_id = _MESSAGE_CAPABILITIES.get(message_type) if isinstance(message_type, str) else None
        if capability_id is None:
            return _error(message, "unknown_type")
        attachment_error = self._validate_attachments(message.get("_attachments", {}))
        if attachment_error is not None:
            return _error(message, attachment_error)
        binding_id = message.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id:
            return _error(message, "binding_unavailable")
        handle = self._resolve_handle(capability_id, binding_id)
        if handle is None:
            return _error(message, "binding_unavailable")
        try:
            return dict(handle.dispatch(message))
        except (CapabilityUnavailable, HostError):
            return _error(message, "host_unavailable")

    def _resolve_handle(self, capability_id: str, binding_id: str) -> Optional[DisplayHandle]:
        if self._runtime is None:
            return self._bindings.get(binding_id)
        bindings = getattr(self._runtime, "bindings", {})
        binding = bindings.get(binding_id)
        if binding is None or getattr(binding, "capability_id", None) != capability_id:
            return None
        try:
            return self._runtime.handle(capability_id, binding_id)
        except CapabilityUnavailable:
            return None

    @staticmethod
    def _validate_attachments(value: object) -> Optional[str]:
        if not isinstance(value, Mapping) or len(value) > MAX_ATTACHMENTS:
            return "invalid_attachments"
        total = 0
        for attachment_id, attachment in value.items():
            if not isinstance(attachment_id, str) or not attachment_id or not isinstance(attachment, bytes):
                return "invalid_attachments"
            total += len(attachment)
            if total > MAX_ATTACHMENT_BYTES:
                return "attachment_too_large"
        return None
