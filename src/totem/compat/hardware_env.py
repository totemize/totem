"""Translate deployed ``TOTEM_*`` names at the compatibility boundary only."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping, Optional


def _enabled(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class LegacyRuntimeConfig:
    """Typed inputs carried from legacy environment names into composition."""

    allow_mock_drivers: bool = False
    storage_root: Optional[str] = None
    bus_url: str = "http://127.0.0.1:8000"


def legacy_runtime_config(environ: Optional[Mapping[str, str]] = None) -> LegacyRuntimeConfig:
    """Read only compatibility names without leaking environment access inward."""

    values = os.environ if environ is None else environ
    root = values.get("TOTEM_STORAGE_ROOT")
    return LegacyRuntimeConfig(
        allow_mock_drivers=_enabled(values.get("TOTEM_ALLOW_MOCK_DRIVERS", "")),
        storage_root=root.strip() if isinstance(root, str) and root.strip() else None,
        bus_url=values.get("TOTEM_HARDWARE_BUS_URL", "http://127.0.0.1:8000").strip()
        or "http://127.0.0.1:8000",
    )
