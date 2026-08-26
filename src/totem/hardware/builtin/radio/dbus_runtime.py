"""Injectable provider-side D-Bus call seam with no bus ownership."""

from __future__ import annotations

from typing import Any, Callable, List, Optional


def variant_value(value: Any) -> Any:
    """Recursively unwrap variant-shaped values without importing a D-Bus backend."""

    if hasattr(value, "signature") and hasattr(value, "value"):
        return variant_value(value.value)
    if isinstance(value, dict):
        return {key: variant_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [variant_value(item) for item in value]
    return value


class DBusRuntime:
    """Tiny injectable carrier used by a selected provider after composition."""

    def __init__(self, call: Callable[..., List[Any]]) -> None:
        self._call = call

    def call(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: Optional[List[Any]] = None,
    ) -> List[Any]:
        return [variant_value(item) for item in self._call(destination, path, interface, member, signature, body or [])]
