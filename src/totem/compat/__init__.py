"""Compatibility-only translators for deployed Totem entry points."""

from .hardware_client import LegacyHardwareClient, LegacyHardwareError
from .hardware_env import LegacyRuntimeConfig, legacy_runtime_config

__all__ = [
    "LegacyHardwareClient",
    "LegacyHardwareError",
    "LegacyRuntimeConfig",
    "legacy_runtime_config",
]
