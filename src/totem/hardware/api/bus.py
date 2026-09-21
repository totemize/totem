"""Generic capability-handle dispatch for canonical hardware bus messages."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from totem.hardware.capabilities.base import CapabilityHandle, CapabilityUnavailable
from totem.hardware.hosts.process import HostError
from totem.hardware.hosts.protocol import MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS


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
        self._bindings: Dict[str, CapabilityHandle] = (
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
        if message_type == "hardware.status.get":
            return self._status_result(message)
        if not isinstance(message_type, str) or "." not in message_type:
            return _error(message, "unknown_type")
        attachment_error = self._validate_attachments(message.get("_attachments", {}))
        if attachment_error is not None:
            return _error(message, attachment_error)
        binding_id = message.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id:
            binding_id = self.default_binding_id(message_type)
        if binding_id is None:
            return _error(message, "binding_unavailable")
        handle = self._resolve_handle(binding_id)
        if handle is None:
            return _error(message, "binding_unavailable")
        try:
            return dict(handle.dispatch(message))
        except (CapabilityUnavailable, HostError):
            return _error(message, "host_unavailable")

    def default_binding_id(self, message_type: str) -> Optional[str]:
        if self._runtime is None:
            return next(iter(self._bindings)) if len(self._bindings) == 1 else None
        selector = getattr(self._runtime, "default_binding_id", None)
        return selector(message_type) if callable(selector) else None

    def _resolve_handle(self, binding_id: str) -> Optional[CapabilityHandle]:
        if self._runtime is None:
            return self._bindings.get(binding_id)
        bindings = getattr(self._runtime, "bindings", {})
        binding = bindings.get(binding_id)
        if binding is None:
            return None
        try:
            return self._runtime.handle(binding.capability_id, binding_id)
        except CapabilityUnavailable:
            return None

    def _status_result(self, message: Mapping[str, Any]) -> Dict[str, Any]:
        """Project only redacted readiness through the canonical bus."""

        if self._runtime is None:
            return _error(message, "host_unavailable")
        try:
            health = self._runtime.health()
        except (AttributeError, CapabilityUnavailable, HostError):
            return _error(message, "host_unavailable")
        return {
            "type": "hardware.status.get.result",
            "id": message["id"],
            "ok": True,
            "status": {
                "ready": bool(health.ready),
                "degraded": bool(health.degraded),
            },
        }

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
