"""Application-facing handles with no provider implementation surface."""

from .base import CapabilityHandle, CapabilityUnavailable
from .display import DisplayHandle
from .nfc import NFCHandle
from .power import PowerHandle
from .storage import StorageHandle

__all__ = [
    "CapabilityHandle",
    "CapabilityUnavailable",
    "DisplayHandle",
    "NFCHandle",
    "PowerHandle",
    "StorageHandle",
]
