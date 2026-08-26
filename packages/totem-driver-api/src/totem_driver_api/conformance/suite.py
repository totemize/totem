"""Ordered, transport-neutral conformance cases for any driver-host adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

from ..messages import normalize_message


@dataclass(frozen=True)
class ConformanceCase:
    """One request/result exchange, retained in the declared execution order."""

    name: str
    message: Mapping[str, object]
    attachments: Optional[Mapping[str, object]] = None
    deadline: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("conformance case name must be non-empty")
        if not isinstance(self.message, Mapping):
            raise ValueError("conformance case message must be an object")
        if self.attachments is not None and not isinstance(self.attachments, Mapping):
            raise ValueError("conformance case attachments must be an object")


@dataclass(frozen=True)
class ConformanceTranscript:
    """A strict ordered functional transcript; containment remains outside it."""

    items: Tuple[Mapping[str, object], ...]


def run_host_conformance(
    host_factory: Callable[[], object], cases: Sequence[ConformanceCase]
) -> ConformanceTranscript:
    """Run startup, declared cases, and idempotent close against one host.

    The returned transcript only removes host-containment fields that are not
    part of the transport-neutral message contract.  It never sorts or
    deduplicates transcript items, so neighboring-case ordering remains a
    first-class conformance assertion.
    """

    host = host_factory()
    items = [{"case": "startup", "result": _normalize_ready(host.await_ready(1.0))}]
    try:
        for case in cases:
            result = host.request(dict(case.message), attachments=case.attachments, deadline=case.deadline)
            items.append({"case": case.name, "result": _normalize_result(result)})
    finally:
        host.close()
        items.append({"case": "close"})
        host.close()
        items.append({"case": "close"})
    return ConformanceTranscript(tuple(items))


def _normalize_ready(value: object) -> Mapping[str, object]:
    plain = _strict_json_object(value)
    plain.pop("generation", None)
    return normalize_message(plain)


def _normalize_result(value: object) -> Mapping[str, object]:
    plain = _strict_json_object(value)
    # Generation and fixture import observations are containment/diagnostic
    # metadata. Functional envelope semantics stay strict and ordered.
    plain.pop("generation", None)
    plain.pop("provider_imported", None)
    return normalize_message(plain)


def _strict_json_object(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("host result must be a JSON object")
    return {str(key): _strict_json_value(item) for key, item in value.items()}


def _strict_json_value(value: Any) -> object:
    if isinstance(value, Mapping):
        return {str(key): _strict_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_strict_json_value(item) for item in value]
    if isinstance(value, list):
        return [_strict_json_value(item) for item in value]
    return value
