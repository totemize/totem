"""Binding-backed storage capability handle."""

from .base import CapabilityHandle


class StorageHandle(CapabilityHandle):
    """Stable storage handle; provider implementation remains runtime-owned."""

