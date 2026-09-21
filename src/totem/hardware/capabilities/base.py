"""Transport-neutral handles for selected capability bindings."""

from __future__ import annotations

from typing import Callable, Dict, Mapping, Optional


class CapabilityUnavailable(RuntimeError):
    """A binding is not currently safe to receive application work."""

    code = "capability_unavailable"


class CapabilityHandle:
    """Route one capability through its opaque binding identity.

    Handles intentionally retain neither the selected provider nor a concrete
    driver object.  The runtime remains the sole owner of the host generation.
    """

    def __init__(
        self,
        capability_id: str,
        binding_id: str,
        dispatch: Callable[[str, str, Mapping[str, object]], Mapping[str, object]],
    ) -> None:
        self.capability_id = capability_id
        self.binding_id = binding_id
        self._dispatch = dispatch

    def dispatch(self, message: Mapping[str, object]) -> Dict[str, object]:
        """Forward a message only through this handle's selected identity."""

        if not isinstance(message, Mapping):
            raise CapabilityUnavailable("capability message must be a mapping")
        requested = message.get("binding_id")
        if requested is not None and requested != self.binding_id:
            raise CapabilityUnavailable("binding identity does not match handle")
        result = self._dispatch(self.capability_id, self.binding_id, dict(message))
        return dict(result)

