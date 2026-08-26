"""Binding-backed power capability handle."""

from .base import CapabilityHandle


class PowerHandle(CapabilityHandle):
    """Stable power handle; provider implementation remains runtime-owned."""

