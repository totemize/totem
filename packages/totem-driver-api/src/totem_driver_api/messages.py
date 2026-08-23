"""Frozen, carrier-neutral message and error value objects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from .identifiers import ContractError


@dataclass(frozen=True)
class ResultError:
    """A stable error safe to expose across driver host boundaries."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ContractError("result error code and message must be non-empty")

    def to_json_value(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class _FrozenArray(tuple):
    """Internal immutable representation of a JSON array."""


class _FrozenObject(tuple):
    """Internal immutable representation of a JSON object."""


def _freeze_json(value: object) -> object:
    """Copy a strict JSON value into immutable containers for public reuse."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if abs(value) > 9007199254740991:
            raise ContractError("JSON integer exceeds the interoperable range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError("JSON number must be finite")
        return value
    if isinstance(value, list):
        return _FrozenArray(_freeze_json(item) for item in value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ContractError("JSON object keys must be strings")
        return _FrozenObject(
            (key, _freeze_json(value[key])) for key in sorted(value)
        )
    raise ContractError("message fields must be strict JSON-compatible values")


def _thaw_json(value: object) -> object:
    """Return a fresh standard-library JSON value from an immutable contract."""
    if isinstance(value, _FrozenArray):
        return [_thaw_json(item) for item in value]
    if isinstance(value, _FrozenObject):
        return {key: _thaw_json(item) for key, item in value}
    return value


@dataclass(frozen=True)
class LogicalMessage:
    """A typed JSON-object envelope with optional request/result correlation."""

    type: str
    id: Optional[str] = None
    fields: Tuple[Tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.type or not self.type.strip():
            raise ContractError("message type must be non-empty")
        if self.id is not None and not self.id:
            raise ContractError("message id must be non-empty when present")
        frozen_fields = []
        keys = set()
        for key, value in self.fields:
            if not isinstance(key, str) or not key or key in {"type", "id"}:
                raise ContractError("message fields require non-reserved string keys")
            if key in keys:
                raise ContractError("message field names must be unique")
            keys.add(key)
            frozen_fields.append((key, _freeze_json(value)))
        object.__setattr__(self, "fields", tuple(frozen_fields))

    def to_json_value(self) -> dict[str, object]:
        value: dict[str, object] = {"type": self.type}
        if self.id is not None:
            value["id"] = self.id
        value.update((key, _thaw_json(field)) for key, field in self.fields)
        return value
