"""Display state contracts shared by controllers and renderers."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ScreenState(str, Enum):
    """High-level screen states; the boot POC implements a useful subset."""

    BOOTING = "booting"
    IDLE = "idle"
    NEW_PEER = "new_peer"
    EXISTING_PEER = "existing_peer"
    ERROR = "error"
    SYNCHRONIZING = "synchronizing"


@dataclass(frozen=True)
class ServiceStatus:
    key: str
    label: str
    ready: bool = False


@dataclass(frozen=True)
class ScreenFrame:
    state: ScreenState
    headline: str = ""
    services: Tuple[ServiceStatus, ...] = ()
