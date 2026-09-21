"""Legacy NFC name translated through the canonical hardware client."""

from __future__ import annotations

from typing import Optional

from totem.compat.hardware_client import LegacyHardwareClient

class NFCManager:
    """Compatibility-only NFC facade; tag reads and writes remain capability calls."""

    def __init__(
        self,
        driver_name: Optional[str] = None,
        *,
        allow_mock: bool = False,
        client: Optional[LegacyHardwareClient] = None,
    ) -> None:
        self.client = client or LegacyHardwareClient()
        self.legacy_config = {"driver_name": driver_name, "allow_mock": allow_mock}
        self._closed = False

    def read_card(self) -> str:
        return self.client.read_card()

    def write_card(self, data: str):
        self.client.write_card(data)

    def close(self) -> None:
        self._closed = True
