"""Bounded immutable lifecycle event publication for runtime consumers."""

from __future__ import annotations

from queue import Empty, Full, Queue
from threading import Lock
from typing import Dict, Optional, Tuple

from totem_driver_api.lifecycle import LifecycleEvent


class RuntimeEventStream:
    """Ordered history plus bounded lossy subscriber queues.

    A subscriber that cannot keep up retains the newest state change and can
    reconcile from ``RuntimeLifecycle.snapshot`` instead of blocking a driver.
    """

    def __init__(self, queue_size: int = 32) -> None:
        if queue_size < 1:
            raise ValueError("event queue size must be positive")
        self._queue_size = queue_size
        self._lock = Lock()
        self._sequence = 0
        self._history: list[LifecycleEvent] = []
        self._subscribers: Dict[int, Queue[LifecycleEvent]] = {}
        self._next_subscriber = 0

    def subscribe(self) -> Queue[LifecycleEvent]:
        with self._lock:
            self._next_subscriber += 1
            subscriber = Queue(maxsize=self._queue_size)
            self._subscribers[self._next_subscriber] = subscriber
            return subscriber

    def publish(
        self,
        binding_id: str,
        previous: object,
        state: object,
        *,
        code: Optional[str] = None,
        details: Optional[Dict[str, object]] = None,
        snapshot: object = None,
    ) -> LifecycleEvent:
        """Publish one event without letting a slow subscriber block progress."""

        with self._lock:
            self._sequence += 1
            event = LifecycleEvent(
                sequence=self._sequence,
                binding_id=binding_id,
                previous=previous,
                state=state,
                code=code,
                details=details or {},
                snapshot=snapshot,
            )
            self._history.append(event)
            for subscriber in self._subscribers.values():
                try:
                    subscriber.put_nowait(event)
                except Full:
                    try:
                        subscriber.get_nowait()
                    except Empty:
                        pass
                    subscriber.put_nowait(event)
            return event

    def history(self) -> Tuple[LifecycleEvent, ...]:
        with self._lock:
            return tuple(self._history)
