"""Generic binding-table dispatch for application hardware messages."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from totem.hardware.capabilities.display import DisplayHandle
from totem.hardware.hosts.process import HostError


def _error(message: Mapping[str, Any], code: str) -> Dict[str, Any]:
    message_type = message.get("type")
    return {
        "type": "{}.result".format(message_type if isinstance(message_type, str) else "error"),
        "id": message.get("id"),
        "ok": False,
        "error": {"code": code},
    }


class HardwareBus:
    """Route request envelopes by resolved binding, never provider family."""

    def __init__(self, bindings: Mapping[str, DisplayHandle]) -> None:
        self._bindings = dict(bindings)

    def dispatch(self, message: Mapping[str, Any]) -> Dict[str, Any]:
        """Return a correlated, stable public result for one bus request."""

        request_id = message.get("id")
        message_type = message.get("type")
        if not isinstance(request_id, str) or not request_id:
            return _error(message, "invalid_request")
        if not isinstance(message_type, str) or message_type != "display.frame.write":
            return _error(message, "unknown_type")
        binding_id = message.get("binding_id")
        if not isinstance(binding_id, str) or binding_id not in self._bindings:
            return _error(message, "binding_unavailable")
        try:
            return self._bindings[binding_id].dispatch(message)
        except HostError:
            return _error(message, "host_unavailable")
