"""Host port shared by isolated and future in-process driver adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Mapping, Optional


class DriverHost(ABC):
    """Transport-neutral logical driver host contract."""

    @abstractmethod
    def request(
        self,
        message: Mapping[str, object],
        attachments: Optional[Mapping[str, object]] = None,
        deadline: Optional[float] = None,
    ) -> Mapping[str, object]:
        raise NotImplementedError

    @abstractmethod
    def events(self) -> Iterable[Mapping[str, object]]:
        raise NotImplementedError

    @abstractmethod
    def close(self, deadline: Optional[float] = None) -> None:
        raise NotImplementedError
