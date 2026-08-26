"""Small provider fixture protocol with no dependency on a Totem daemon."""

from __future__ import annotations

from typing import Mapping, Protocol


class ConformanceProvider(Protocol):
    """The narrow provider shape used by portable conformance fixtures."""

    def write_frame(self, request: object) -> Mapping[str, object]:
        """Accept one public frame request and return its public result fields."""


class FixtureProvider:
    """No-I/O provider usable by third-party host-conformance test fixtures."""

    def write_frame(self, request: object) -> Mapping[str, object]:
        attachment_id = getattr(request, "attachment_id", None)
        if not isinstance(attachment_id, str) or not attachment_id:
            raise ValueError("missing attachment id")
        return {"attachment_id": attachment_id, "accepted": True}
