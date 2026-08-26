"""Public storage compatibility facade and value exports."""

from .device import Storage, StorageDeviceInterface
from .files import BytesLike, ConfinedStorage, StorageOptionsError, StoragePathError

__all__ = [
    "BytesLike",
    "ConfinedStorage",
    "Storage",
    "StorageDeviceInterface",
    "StorageOptionsError",
    "StoragePathError",
]
