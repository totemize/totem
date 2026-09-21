"""Legacy UPS name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient


class UPSManager:
    """Compatibility-only UPS facade; telemetry ownership stays in the runtime."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name}
        self._closed = False

    def get_status(self):
        return self.client.get_ups_status()

    def close(self) -> None:
        self._closed = True
