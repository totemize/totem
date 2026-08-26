"""Public, bounded contract for root-scoped storage file operations."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Tuple

from ..identifiers import CapabilityId, ContractError


STORAGE_FILES = CapabilityId("storage.files", 1)
STORAGE_MAX_PATH_LENGTH = 1024
STORAGE_MAX_PAYLOAD_BYTES = 4096


@dataclass(frozen=True)
class StoragePath:
    """A normalized relative POSIX path, never an absolute filesystem path."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value:
            raise ContractError("storage path must be a non-empty relative path")
        if len(self.value) > STORAGE_MAX_PATH_LENGTH:
            raise ContractError("storage path exceeds maximum length")
        if "\\x00" in self.value or "\\" in self.value:
            raise ContractError("storage path must use relative POSIX components")
        path = PurePosixPath(self.value)
        if path.is_absolute() or any(part == ".." for part in path.parts):
            raise ContractError("storage path must be relative and must not traverse")
        normalized = str(path)
        if normalized == "":
            normalized = "."
        object.__setattr__(self, "value", normalized)


def _payload(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise ContractError("storage payload must be bytes")
    if len(value) > STORAGE_MAX_PAYLOAD_BYTES:
        raise ContractError("storage payload exceeds maximum size")
    return value


@dataclass(frozen=True)
class StorageWriteRequest:
    """One normalized bounded write request decoded before provider dispatch."""

    path: StoragePath
    data: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.path, StoragePath):
            raise ContractError("storage write request requires a storage path")
        object.__setattr__(self, "data", _payload(self.data))

    @classmethod
    def from_json_value(cls, value: object) -> "StorageWriteRequest":
        if not isinstance(value, dict) or set(value) != {"path", "data_b64"}:
            raise ContractError("storage write request must contain only path and data_b64")
        encoded = value["data_b64"]
        if not isinstance(encoded, str):
            raise ContractError("storage data_b64 must be a string")
        try:
            data = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError) as exc:
            raise ContractError("storage data_b64 is invalid") from exc
        return cls(StoragePath(value["path"]), data)

    def to_json_value(self) -> dict[str, object]:
        return {
            "path": self.path.value,
            "data_b64": base64.b64encode(self.data).decode("ascii"),
        }


@dataclass(frozen=True)
class StorageReadResult:
    """A bounded binary read result encoded in strict JSON-safe base64."""

    data: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _payload(self.data))

    def to_json_value(self) -> dict[str, object]:
        return {"data_b64": base64.b64encode(self.data).decode("ascii")}


@dataclass(frozen=True)
class StorageListResult:
    """Deterministic normalized relative paths without file contents."""

    paths: Tuple[StoragePath, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.paths, tuple) or not all(isinstance(path, StoragePath) for path in self.paths):
            raise ContractError("storage list result requires normalized paths")
        object.__setattr__(self, "paths", tuple(sorted(self.paths, key=lambda path: path.value)))

    def to_json_value(self) -> dict[str, object]:
        return {"paths": [path.value for path in self.paths]}


@dataclass(frozen=True)
class StorageDeleteResult:
    """Explicit successful delete acknowledgement."""

    deleted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.deleted, bool):
            raise ContractError("storage deleted must be boolean")

    def to_json_value(self) -> dict[str, object]:
        return {"deleted": self.deleted}
