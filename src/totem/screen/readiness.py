"""Live and synthesized service-readiness monitors."""

import asyncio
import json
from typing import Dict, Iterable, Sequence, Set

from totem.screen.display import DeviceManagerDisplay
from totem.screen.model import ServiceStatus

SERVICE_SPECS = (
    ServiceStatus("device", "Device API"),
    ServiceStatus("fips", "FIPS mesh"),
    ServiceStatus("relay", "Nostr relay"),
    ServiceStatus("totemd", "Control plane"),
)


async def _json_command(*argv: str) -> Dict:
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await asyncio.wait_for(process.communicate(), timeout=3.0)
    if process.returncode != 0:
        return {}
    try:
        return json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


class LiveReadinessMonitor:
    """Probe the useful interface of each boot service, not its log output."""

    def __init__(self, display: DeviceManagerDisplay):
        self.display = display

    async def _fips_ready(self) -> bool:
        status = await _json_command("fipsctl", "show", "status")
        return status.get("state") == "running" and status.get("tun_state") == "active"

    @staticmethod
    async def _relay_ready() -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("::1", 7777), timeout=1.0
            )
        except (OSError, asyncio.TimeoutError):
            return False
        writer.close()
        await writer.wait_closed()
        return True

    @staticmethod
    async def _totemd_ready() -> bool:
        response = await _json_command("totemctl", "status")
        return response.get("ok") is True

    async def snapshot(self) -> Set[str]:
        results = await asyncio.gather(
            self.display.ready(),
            self._fips_ready(),
            self._relay_ready(),
            self._totemd_ready(),
            return_exceptions=True,
        )
        return {
            service.key
            for service, result in zip(SERVICE_SPECS, results)
            if result is True
        }


class SyntheticReadinessMonitor:
    """Bring one service online per snapshot for deterministic replay."""

    def __init__(self, services: Sequence[ServiceStatus] = SERVICE_SPECS):
        self._keys = [service.key for service in services]
        self._ready_count = 0

    async def snapshot(self) -> Set[str]:
        result = set(self._keys[: self._ready_count])
        if self._ready_count < len(self._keys):
            self._ready_count += 1
        return result


def statuses(ready: Iterable[str]):
    ready_keys = set(ready)
    return tuple(
        ServiceStatus(service.key, service.label, service.key in ready_keys)
        for service in SERVICE_SPECS
    )
