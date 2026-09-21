"""Binding-backed display capability handle."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

from .base import CapabilityHandle


class DisplayHandle(CapabilityHandle):
    """Expose one selected display binding without a provider-specific API."""

    def __init__(
        self,
        binding_id: str,
        host: Optional[Any] = None,
        *,
        capability_id: str = "display.frame-sink@1",
        dispatch: Optional[Callable[[str, str, Mapping[str, object]], Mapping[str, object]]] = None,
    ) -> None:
        if dispatch is None:
            if host is None:
                raise ValueError("display handle requires a host or runtime dispatch")

            def dispatch(_capability_id: str, selected_binding_id: str, message: Mapping[str, object]) -> Mapping[str, object]:
                request = dict(message)
                request.setdefault("binding_id", selected_binding_id)
                return host.request(request)

        super().__init__(capability_id, binding_id, dispatch)

    def dispatch(self, message: Mapping[str, Any]) -> Dict[str, Any]:
        """Forward one logical display frame request through its selected host."""

        return super().dispatch(message)
