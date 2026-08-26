"""Frozen, carrier-neutral NIP-5D-shaped message value objects."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple, Union

from .identifiers import ContractError


_TYPE_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")
_ERROR_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_JSON_DEPTH = 64
JSON_INTEGER_MIN = -(2**63)
JSON_INTEGER_MAX = 2**63 - 1


@dataclass(frozen=True)
class ResultError:
    """A stable, bounded error safe to expose across driver host boundaries."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not _ERROR_CODE_RE.fullmatch(self.code):
            raise ContractError("result error code must be a stable lower-case identifier")
        if (
            not isinstance(self.message, str)
            or not self.message.strip()
            or len(self.message) > 256
            or "traceback" in self.message.lower()
            or "\n" in self.message
            or "\r" in self.message
        ):
            raise ContractError("result error message must be a stable public message")

    def to_json_value(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class AttachmentDescriptor:
    """Metadata for one raw carrier attachment, never an inline JSON value."""

    id: str
    media_type: str
    length: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ContractError("attachment id must be non-empty")
        if not isinstance(self.media_type, str) or not self.media_type or "/" not in self.media_type:
            raise ContractError("attachment media type must be non-empty")
        if isinstance(self.length, bool) or not isinstance(self.length, int) or self.length < 0:
            raise ContractError("attachment length must be a non-negative integer")
        if not isinstance(self.sha256, str) or not _SHA256_RE.fullmatch(self.sha256):
            raise ContractError("attachment SHA-256 must be lowercase hexadecimal")

    def to_json_value(self) -> Dict[str, object]:
        return {"id": self.id, "media_type": self.media_type, "length": self.length, "sha256": self.sha256}

    @classmethod
    def from_json_value(cls, value: object) -> "AttachmentDescriptor":
        if not isinstance(value, Mapping) or set(value) != {"id", "media_type", "length", "sha256"}:
            raise ContractError("attachment descriptor has invalid fields")
        return cls(value["id"], value["media_type"], value["length"], value["sha256"])


class _FrozenArray(tuple):
    """Internal immutable representation of a JSON array."""


class _FrozenObject(tuple):
    """Internal immutable representation of a JSON object."""


def freeze_json_value(value: object, depth: int = 0) -> object:
    """Copy a strict JSON value into immutable containers for concurrent reuse."""
    if depth > _MAX_JSON_DEPTH:
        raise ContractError("JSON value nesting exceeds 64 levels")
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if not JSON_INTEGER_MIN <= value <= JSON_INTEGER_MAX:
            raise ContractError("JSON integer is outside the signed 64-bit range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError("JSON number must be finite")
        return value
    if isinstance(value, list):
        return _FrozenArray(freeze_json_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ContractError("JSON object keys must be strings")
        return _FrozenObject((key, freeze_json_value(value[key], depth + 1)) for key in sorted(value))
    raise ContractError("message fields must be strict JSON-compatible values")


def thaw_json_value(value: object) -> object:
    """Return a fresh standard-library JSON value from an immutable contract."""
    if isinstance(value, _FrozenArray):
        return [thaw_json_value(item) for item in value]
    if isinstance(value, _FrozenObject):
        return {key: thaw_json_value(item) for key, item in value}
    return value


def _validate_type(value: object) -> str:
    if not isinstance(value, str) or not _TYPE_RE.fullmatch(value):
        raise ContractError("message type must be a lower-case domain.action string")
    return value


@dataclass(frozen=True)
class LogicalMessage:
    """A typed JSON-object envelope with optional request/result correlation."""

    type: str
    id: Optional[str] = None
    fields: Tuple[Tuple[str, object], ...] = ()
    ok: Optional[bool] = None
    error: Optional[ResultError] = None

    def __post_init__(self) -> None:
        _validate_type(self.type)
        if self.id is not None and (not isinstance(self.id, str) or not self.id.strip()):
            raise ContractError("message id must be non-empty when present")
        is_result = self.type.endswith(".result")
        if is_result:
            if self.id is None or not isinstance(self.ok, bool):
                raise ContractError("results require a request id and boolean ok field")
            if self.ok and self.error is not None:
                raise ContractError("successful results cannot contain an error")
            if not self.ok and not isinstance(self.error, ResultError):
                raise ContractError("failed results require one structured error")
        elif self.ok is not None or self.error is not None:
            raise ContractError("only result messages may contain ok or error")

        frozen_fields = []
        keys = set()
        for key, value in self.fields:
            if not isinstance(key, str) or not key or key in {"type", "id", "ok", "error", "_attachments", "_attachment_media_types"}:
                raise ContractError("message fields require non-reserved string keys")
            if key in keys:
                raise ContractError("message field names must be unique")
            keys.add(key)
            frozen_fields.append((key, freeze_json_value(value)))
        object.__setattr__(self, "fields", tuple(frozen_fields))

    @classmethod
    def request(cls, message_type: str, request_id: Optional[str] = None, fields: Optional[Mapping[str, object]] = None) -> "LogicalMessage":
        if message_type.endswith(".result"):
            raise ContractError("requests cannot use a result type")
        return cls(message_type, request_id, tuple((fields or {}).items()))

    @classmethod
    def result_for(cls, request: Union["LogicalMessage", Mapping[str, object]], fields: Optional[Mapping[str, object]] = None) -> "LogicalMessage":
        request_value = normalize_message(request)
        request_type = request_value["type"]
        request_id = request_value.get("id")
        if not isinstance(request_type, str) or not isinstance(request_id, str):
            raise ContractError("results require an id-bearing request")
        return cls(request_type + ".result", request_id, tuple((fields or {}).items()), ok=True)

    @classmethod
    def from_json_value(cls, value: object) -> "LogicalMessage":
        if not isinstance(value, Mapping):
            raise ContractError("logical message must be a JSON object")
        message_type = _validate_type(value.get("type"))
        request_id = value.get("id")
        if "id" in value and (not isinstance(request_id, str) or not request_id.strip()):
            raise ContractError("message id must be non-empty when present")
        if message_type.endswith(".result"):
            ok = value.get("ok")
            error_value = value.get("error")
            error = None
            if error_value is not None:
                if not isinstance(error_value, Mapping) or set(error_value) != {"code", "message"}:
                    raise ContractError("result error must have code and message")
                error = ResultError(error_value["code"], error_value["message"])
            fields = tuple((key, field) for key, field in value.items() if key not in {"type", "id", "ok", "error"})
            return cls(message_type, request_id, fields, ok=ok, error=error)
        if "ok" in value or "error" in value:
            raise ContractError("only result messages may contain ok or error")
        return cls(message_type, request_id, tuple((key, field) for key, field in value.items() if key not in {"type", "id"}))

    def to_json_value(self) -> Dict[str, object]:
        value: Dict[str, object] = {"type": self.type}
        if self.id is not None:
            value["id"] = self.id
        if self.type.endswith(".result"):
            value["ok"] = self.ok
            if self.error is not None:
                value["error"] = self.error.to_json_value()
        value.update((key, thaw_json_value(field)) for key, field in self.fields)
        return value


def normalize_message(message: Union[LogicalMessage, Mapping[str, object]]) -> Dict[str, object]:
    """Return a fresh strict JSON transcript for process, in-process, and HTTP carriers."""
    if isinstance(message, LogicalMessage):
        return message.to_json_value()
    return LogicalMessage.from_json_value(message).to_json_value()


def error_result(request: Union[LogicalMessage, Mapping[str, object]], code: str, message: str) -> Dict[str, object]:
    """Create one safe structured result without exposing an internal exception."""
    request_value = normalize_message(request)
    request_type = request_value.get("type")
    request_id = request_value.get("id")
    if not isinstance(request_type, str) or not isinstance(request_id, str):
        raise ContractError("errors require an id-bearing request")
    error = ResultError(code, message)
    return LogicalMessage(request_type + ".result", request_id, (), ok=False, error=error).to_json_value()


def unknown_type_result(message: Union[LogicalMessage, Mapping[str, object]]) -> Optional[Dict[str, object]]:
    """Apply the NIP-5D/totemd rule: ignore pushes, correlate unknown requests."""
    normalized = normalize_message(message)
    if normalized.get("id") is None:
        return None
    return error_result(normalized, "unknown_type", "unknown type: " + str(normalized["type"]))


class PendingRequests:
    """Correlation state for exactly one host generation."""

    def __init__(self, generation: str) -> None:
        if not isinstance(generation, str) or not generation:
            raise ContractError("pending request generation must be non-empty")
        self.generation = generation
        self._pending: Dict[str, str] = {}

    def register(self, request: Union[LogicalMessage, Mapping[str, object]]) -> Dict[str, object]:
        normalized = normalize_message(request)
        request_id = normalized.get("id")
        request_type = normalized.get("type")
        if not isinstance(request_id, str) or not isinstance(request_type, str) or request_type.endswith(".result"):
            raise ContractError("only id-bearing requests can be pending")
        if request_id in self._pending:
            raise ContractError("duplicate request id in host generation")
        self._pending[request_id] = request_type
        return normalized

    def consume(self, result: Union[LogicalMessage, Mapping[str, object]]) -> Optional[Dict[str, object]]:
        normalized = normalize_message(result)
        result_id = normalized.get("id")
        result_type = normalized.get("type")
        if not isinstance(result_id, str) or not isinstance(result_type, str) or not result_type.endswith(".result"):
            return None
        expected_type = self._pending.get(result_id)
        if expected_type is None or result_type != expected_type + ".result":
            return None
        del self._pending[result_id]
        return normalized
