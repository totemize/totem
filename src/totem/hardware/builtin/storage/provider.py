"""Child-only, lease-gated storage provider with a confined local root."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional, Protocol, Tuple

from totem_driver_api import ResourceClaim
from totem_driver_api.capabilities.storage import (
    StorageDeleteResult,
    StorageListResult,
    StoragePath,
    StorageReadResult,
    StorageWriteRequest,
)

from .files import ConfinedStorage, StoragePathError


_REQUIRED_CLAIMS = frozenset(
    {("path", "storage-root"), ("mount", "storage-mount"), ("block", "storage-block")}
)
_SUPPORTED_MODELS = frozenset({"filesystem", "generic_nvme"})


class StorageSelectionError(ValueError):
    """Selection or leases failed before a driver can access the filesystem."""


class StorageDriver(Protocol):
    def init(self) -> bool:
        """Initialize the selected storage implementation."""

    def read_file(self, file_path: str) -> bytes:
        """Read one already-confined relative file."""

    def write_file(self, file_path: str, data: bytes, options: Optional[Mapping[str, object]] = None) -> bool:
        """Write one already-confined relative file."""

    def list_files(self, file_path: str = ".") -> tuple[str, ...]:
        """List already-confined relative files."""

    def delete_file(self, file_path: str) -> bool:
        """Delete one already-confined relative file."""


class StorageProvider:
    """Expose a selected, claimed filesystem or NVMe root through storage.files@1."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        root: Optional[object] = None,
        claims: Iterable[ResourceClaim] = (),
        driver: Optional[StorageDriver] = None,
    ) -> None:
        self._model = model.strip().casefold() if isinstance(model, str) else None
        self._claims: Tuple[ResourceClaim, ...] = tuple(claims)
        self._driver = driver
        self._confined = ConfinedStorage(root) if root is not None else None
        self._initialized = False
        self.driver_io_count = 0

    def read(self, requested_path: str) -> StorageReadResult:
        path, driver = self._prepare_file(requested_path)
        self.driver_io_count += 1
        return StorageReadResult(driver.read_file(path))

    def write(self, requested_path: str, data: bytes) -> bool:
        request = StorageWriteRequest(self._protocol_path(requested_path), data)
        path, driver = self._prepare_file(request.path.value)
        self.driver_io_count += 1
        return driver.write_file(path, request.data)

    def list(self, requested_path: str = ".") -> StorageListResult:
        path, driver = self._prepare_directory(requested_path)
        self.driver_io_count += 1
        return StorageListResult(tuple(StoragePath(value) for value in driver.list_files(path)))

    def delete(self, requested_path: str) -> StorageDeleteResult:
        path, driver = self._prepare_file(requested_path)
        self.driver_io_count += 1
        return StorageDeleteResult(driver.delete_file(path))

    def _prepare_file(self, requested_path: str) -> tuple[str, StorageDriver]:
        path = self._protocol_path(requested_path)
        driver = self._require_ready_driver()
        assert self._confined is not None
        self._confined.resolve(path.value)
        return path.value, driver

    def _prepare_directory(self, requested_path: str) -> tuple[str, StorageDriver]:
        path = self._protocol_path(requested_path)
        driver = self._require_ready_driver()
        assert self._confined is not None
        self._confined.resolve_directory(path.value)
        return path.value, driver

    @staticmethod
    def _protocol_path(requested_path: str) -> StoragePath:
        try:
            return StoragePath(requested_path)
        except ValueError as exc:
            raise StoragePathError("Storage path is invalid") from exc

    def _require_ready_driver(self) -> StorageDriver:
        declared_claims = frozenset(
            (claim.kind.strip().casefold(), claim.identifier.strip().casefold()) for claim in self._claims
        )
        if not _REQUIRED_CLAIMS.issubset(declared_claims):
            raise StorageSelectionError("storage root, mount, and block claims are incomplete")
        if self._model not in _SUPPORTED_MODELS:
            raise StorageSelectionError("storage model is not declared")
        if self._confined is None:
            raise StorageSelectionError("storage root is unavailable until child composition")
        if self._driver is None:
            raise StorageSelectionError("storage driver is unavailable until child composition")
        if not self._initialized:
            if self._driver.init() is False:
                raise StorageSelectionError("storage driver failed to initialize")
            self._initialized = True
        return self._driver


def create_provider() -> StorageProvider:
    """Return a side-effect-free provider product after catalog resolution."""

    return StorageProvider()
