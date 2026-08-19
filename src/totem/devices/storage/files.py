"""Confined, binary-safe file operations shared by storage drivers."""

import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Mapping, Optional, Union


class StoragePathError(ValueError):
    """Raised when a requested path escapes the configured storage root."""


class StorageOptionsError(ValueError):
    """Raised when unsupported or invalid write options are supplied."""


BytesLike = Union[bytes, bytearray, memoryview]


class ConfinedStorage:
    """Perform file operations below one resolved storage root."""

    _OPTION_NAMES = frozenset(("append", "atomic", "sync", "permissions"))

    def __init__(self, root: Union[str, os.PathLike]):
        self.root = Path(root).expanduser().resolve()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, requested_path: Union[str, os.PathLike]) -> Path:
        requested = Path(requested_path)
        if requested.is_absolute():
            raise StoragePathError("Storage paths must be relative to the storage root")

        candidate = (self.root / requested).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StoragePathError(
                "Storage path escapes configured root: {}".format(requested_path)
            ) from exc
        if candidate == self.root:
            raise StoragePathError("Storage path must identify a file")
        return candidate

    @classmethod
    def normalize_options(
        cls, options: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        supplied = dict(options or {})
        unknown = set(supplied).difference(cls._OPTION_NAMES)
        if unknown:
            raise StorageOptionsError(
                "Unsupported storage options: {}".format(
                    ", ".join(sorted(unknown))
                )
            )

        normalized = {
            "append": False,
            "atomic": True,
            "sync": False,
            "permissions": None,
        }
        normalized.update(supplied)
        for name in ("append", "atomic", "sync"):
            if not isinstance(normalized[name], bool):
                raise StorageOptionsError("{} must be a boolean".format(name))
        permissions = normalized["permissions"]
        if permissions is not None and not isinstance(permissions, int):
            raise StorageOptionsError("permissions must be an integer or None")
        return normalized

    def read(self, requested_path: Union[str, os.PathLike]) -> bytes:
        path = self.resolve(requested_path)
        with path.open("rb") as file:
            return file.read()

    def write(
        self,
        requested_path: Union[str, os.PathLike],
        data: BytesLike,
        options: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("Storage writes require bytes-like data")

        payload = bytes(data)
        config = self.normalize_options(options)
        path = self.resolve(requested_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if config["atomic"]:
            self._atomic_write(path, payload, config["append"], config["sync"])
        else:
            mode = "ab" if config["append"] else "wb"
            with path.open(mode) as file:
                file.write(payload)
                if config["sync"]:
                    file.flush()
                    os.fsync(file.fileno())

        if config["permissions"] is not None:
            path.chmod(config["permissions"])
        return True

    @staticmethod
    def _atomic_write(path: Path, data: bytes, append: bool, sync: bool) -> None:
        descriptor, temp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=".{}.".format(path.name), suffix=".tmp"
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as file:
                if append and path.exists():
                    with path.open("rb") as source:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            file.write(chunk)
                file.write(data)
                if sync:
                    file.flush()
                    os.fsync(file.fileno())
            os.replace(str(temp_path), str(path))
        except Exception:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            raise
