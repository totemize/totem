"""Compatibility facade for the screen frame-sink port."""

from totem.screen.adapters.hardware_bus import HardwareBusScreenAdapter


class DeviceManagerDisplay(HardwareBusScreenAdapter):
    """Historical display import backed solely by the canonical hardware bus."""
