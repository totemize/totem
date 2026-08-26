"""Lossy, typed SSE projection over runtime lifecycle events."""

from __future__ import annotations

import asyncio
import json
from queue import Empty, Queue
from typing import AsyncIterator, Dict, Mapping


_REDACTED_KEYS = frozenset(("credential", "secret", "token", "traceback"))


def _value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _value(item) for key, item in value.items() if str(key).lower() not in _REDACTED_KEYS}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    return "redacted"


class HardwareEventProjection:
    """Project lifecycle events as ordered, bounded, safe SSE values."""

    def __init__(self, events: object) -> None:
        self._events = events

    @property
    def dropped_events(self) -> int:
        """Expose lossy queue backpressure without exposing queued payloads."""

        return int(getattr(self._events, "dropped_events", 0))

    def project_history(self) -> list[Dict[str, object]]:
        return [self.project(event) for event in self._events.history()]

    def project(self, event: object) -> Dict[str, object]:
        previous = getattr(event.previous, "value", event.previous)
        state = getattr(event.state, "value", event.state)
        return {
            "type": "hardware.lifecycle",
            "sequence": event.sequence,
            "binding_id": event.binding_id,
            "previous": previous,
            "state": state,
            "code": event.code,
            "details": _value(event.details),
            "dropped_events": self.dropped_events,
        }

    async def stream(self) -> AsyncIterator[bytes]:
        subscriber: Queue[object] = self._events.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 0.25)
                except Empty:
                    continue
                payload = json.dumps(self.project(event), sort_keys=True, separators=(",", ":"))
                yield "event: hardware.lifecycle\ndata: {}\n\n".format(payload).encode("utf-8")
        finally:
            self._events.unsubscribe(subscriber)
