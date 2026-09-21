"""Binding-backed Bluetooth capability handle."""

from ..base import CapabilityHandle


class BluetoothHandle(CapabilityHandle):
    """Stable Bluetooth handle; provider implementation remains runtime-owned."""

