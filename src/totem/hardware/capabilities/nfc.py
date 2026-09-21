"""Binding-backed NFC capability handle."""

from .base import CapabilityHandle


class NFCHandle(CapabilityHandle):
    """Stable NFC handle; provider implementation remains runtime-owned."""

