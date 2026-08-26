"""Compatibility re-exports for provider-owned confined storage values."""

from totem.hardware.builtin.storage.files import BytesLike, ConfinedStorage, StorageOptionsError, StoragePathError

__all__ = ["BytesLike", "ConfinedStorage", "StorageOptionsError", "StoragePathError"]
