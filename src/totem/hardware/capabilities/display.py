"""Binding-backed display capability handle."""

from __future__ import annotations

from typing import Any, Dict, Mapping


class DisplayHandle:
    """Expose one selected display binding without a provider-specific API."""

    def __init__(self, binding_id: str, host: Any) -> None:
        self.binding_id = binding_id
        self._host = host

    def dispatch(self, message: Mapping[str, Any]) -> Dict[str, Any]:
        """Forward one logical display frame request through its selected host."""

        return self._host.request(dict(message))
