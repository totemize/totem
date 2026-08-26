"""Explicit binding lifecycle state, health snapshots, and close ordering."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, RLock
from typing import Callable, Dict, Mapping, Optional, Tuple

from totem_driver_api.lifecycle import BindingState, HealthState

from .events import RuntimeEventStream


_UNSET = object()

_LEGAL_TRANSITIONS: Mapping[BindingState, Tuple[BindingState, ...]] = {
    BindingState.DISCOVERED: (BindingState.MATCHED, BindingState.FAILED, BindingState.STOPPING, BindingState.CLOSED),
    BindingState.MATCHED: (BindingState.BOUND, BindingState.FAILED, BindingState.STOPPING, BindingState.CLOSED),
    BindingState.BOUND: (BindingState.STARTING, BindingState.FAILED, BindingState.STOPPING, BindingState.CLOSED),
    BindingState.STARTING: (BindingState.READY, BindingState.DEGRADED, BindingState.FAILED, BindingState.RETRYING, BindingState.STOPPING),
    BindingState.READY: (BindingState.DEGRADED, BindingState.FAILED, BindingState.STOPPING),
    BindingState.DEGRADED: (BindingState.READY, BindingState.FAILED, BindingState.STOPPING),
    BindingState.FAILED: (BindingState.RETRYING, BindingState.QUARANTINED, BindingState.STOPPING, BindingState.CLOSED),
    BindingState.RETRYING: (BindingState.STARTING, BindingState.FAILED, BindingState.QUARANTINED, BindingState.STOPPING),
    BindingState.QUARANTINED: (BindingState.STARTING, BindingState.STOPPING, BindingState.CLOSED),
    BindingState.CONTAMINATED: (BindingState.STOPPING, BindingState.CLOSED),
    BindingState.STOPPING: (BindingState.FAILED, BindingState.CLOSED),
    BindingState.CLOSED: (),
}


class LifecycleTransitionError(ValueError):
    """Stable evidence for an attempted skipped or neighboring transition."""

    code = "invalid_transition"

    def __init__(self, previous: BindingState, requested: BindingState) -> None:
        self.previous = previous
        self.requested = requested
        super().__init__("invalid lifecycle transition: {} -> {}".format(previous.value, requested.value))


@dataclass(frozen=True)
class BindingSnapshot:
    """Complete immutable diagnostic state for one binding generation."""

    binding_id: str
    required: bool
    mode: str
    process_group: str
    state: BindingState
    health: HealthState
    generation: int
    restart_count: int
    quarantined: bool
    contaminated: bool
    exit_code: Optional[int]
    held_leases: Tuple[str, ...]


@dataclass(frozen=True)
class RuntimeSnapshot:
    """Reconcileable runtime health state, including the valid empty runtime."""

    bindings: Mapping[str, BindingSnapshot]
    ready: bool
    health: HealthState
    closed: bool


def legal_transitions() -> Mapping[BindingState, Tuple[BindingState, ...]]:
    """Return the public transition table without exposing mutable state."""

    return dict(_LEGAL_TRANSITIONS)


def _health_for(state: BindingState) -> HealthState:
    if state is BindingState.READY:
        return HealthState.READY
    if state is BindingState.DEGRADED:
        return HealthState.DEGRADED
    if state is BindingState.CLOSED:
        return HealthState.CLOSED
    return HealthState.FAILED


class BindingLifecycle:
    """Locked explicit state record for one binding, independent of host mode."""

    def __init__(
        self,
        binding_id: str,
        *,
        required: bool,
        mode: str = "process",
        process_group: str = "provider",
        held_leases: Tuple[str, ...] = (),
    ) -> None:
        if not binding_id:
            raise ValueError("binding id is required")
        self.binding_id = binding_id
        self.required = required
        self.mode = mode
        self.process_group = process_group
        self._lock = RLock()
        self._state = BindingState.DISCOVERED
        self._generation = 0
        self._restart_count = 0
        self._quarantined = False
        self._contaminated = False
        self._exit_code: Optional[int] = None
        self._held_leases = tuple(held_leases)

    def force_state_for_test(self, state: BindingState) -> None:
        """Construct every transition-table edge deterministically in unit tests."""

        with self._lock:
            self._state = state

    def snapshot(self) -> BindingSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def transition(
        self,
        requested: BindingState,
        *,
        generation: object = _UNSET,
        restart_count: object = _UNSET,
        exit_code: object = _UNSET,
        held_leases: object = _UNSET,
    ) -> BindingSnapshot:
        """Make exactly one permitted transition or preserve the current record."""

        with self._lock:
            previous = self._state
            if requested not in _LEGAL_TRANSITIONS[previous]:
                raise LifecycleTransitionError(previous, requested)
            self._state = requested
            if generation is not _UNSET:
                self._generation = int(generation)
            if restart_count is not _UNSET:
                self._restart_count = int(restart_count)
            if exit_code is not _UNSET:
                self._exit_code = exit_code if exit_code is None else int(exit_code)
            if held_leases is not _UNSET:
                self._held_leases = tuple(held_leases)
            self._quarantined = requested is BindingState.QUARANTINED
            self._contaminated = requested is BindingState.CONTAMINATED
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> BindingSnapshot:
        return BindingSnapshot(
            binding_id=self.binding_id,
            required=self.required,
            mode=self.mode,
            process_group=self.process_group,
            state=self._state,
            health=_health_for(self._state),
            generation=self._generation,
            restart_count=self._restart_count,
            quarantined=self._quarantined,
            contaminated=self._contaminated,
            exit_code=self._exit_code,
            held_leases=self._held_leases,
        )


class RuntimeLifecycle:
    """Own binding records, derived readiness, event sequencing, and shutdown."""

    def __init__(self, *, events: Optional[RuntimeEventStream] = None) -> None:
        self._lock = RLock()
        self._events = events or RuntimeEventStream()
        self._bindings: Dict[str, BindingLifecycle] = {}
        self._closed = False

    @property
    def events(self) -> RuntimeEventStream:
        return self._events

    def add_binding(
        self,
        binding_id: str,
        *,
        required: bool,
        mode: str = "process",
        process_group: str = "provider",
        held_leases: Tuple[str, ...] = (),
    ) -> BindingSnapshot:
        with self._lock:
            if self._closed:
                raise RuntimeError("runtime is closed")
            if binding_id in self._bindings:
                raise ValueError("binding is already registered")
            lifecycle = BindingLifecycle(
                binding_id,
                required=required,
                mode=mode,
                process_group=process_group,
                held_leases=held_leases,
            )
            self._bindings[binding_id] = lifecycle
            snapshot = lifecycle.snapshot()
        self._publish(snapshot, previous=None)
        return snapshot

    def transition(self, binding_id: str, requested: BindingState, *, code: Optional[str] = None, **values: object) -> BindingSnapshot:
        with self._lock:
            lifecycle = self._bindings[binding_id]
            previous = lifecycle.snapshot().state
            snapshot = lifecycle.transition(requested, **values)
        self._publish(snapshot, previous=previous, code=code)
        return snapshot

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            bindings = {binding_id: lifecycle.snapshot() for binding_id, lifecycle in self._bindings.items()}
            closed = self._closed
        required = tuple(snapshot for snapshot in bindings.values() if snapshot.required)
        ready = not closed and all(snapshot.state in (BindingState.READY, BindingState.DEGRADED) for snapshot in required)
        if closed:
            health = HealthState.CLOSED
        elif any(snapshot.required and snapshot.state not in (BindingState.READY, BindingState.DEGRADED) for snapshot in bindings.values()):
            health = HealthState.FAILED
        elif any(snapshot.state is not BindingState.READY for snapshot in bindings.values()):
            health = HealthState.DEGRADED
        else:
            health = HealthState.READY
        return RuntimeSnapshot(bindings=bindings, ready=ready, health=health, closed=closed)

    def close(self, close_host: Optional[Callable[[BindingSnapshot], None]] = None) -> RuntimeSnapshot:
        """Close hosts first, then move records/runtime to an idempotent close."""

        with self._lock:
            if self._closed:
                return self.snapshot()
            lifecycles = tuple(self._bindings.values())
        for lifecycle in lifecycles:
            before = lifecycle.snapshot()
            if before.state is BindingState.CLOSED:
                continue
            if close_host is not None:
                close_host(before)
            current = lifecycle.snapshot().state
            if current is not BindingState.STOPPING:
                snapshot = lifecycle.transition(BindingState.STOPPING)
                self._publish(snapshot, previous=current)
            snapshot = lifecycle.transition(BindingState.CLOSED)
            self._publish(snapshot, previous=BindingState.STOPPING)
        with self._lock:
            self._closed = True
        return self.snapshot()

    def _publish(self, snapshot: BindingSnapshot, *, previous: Optional[BindingState], code: Optional[str] = None) -> None:
        self._events.publish(
            snapshot.binding_id,
            previous,
            snapshot.state,
            code=code,
            details={
                "generation": snapshot.generation,
                "restart_count": snapshot.restart_count,
                "quarantined": snapshot.quarantined,
                "contaminated": snapshot.contaminated,
                "exit_code": snapshot.exit_code,
                "held_leases": snapshot.held_leases,
            },
            snapshot=snapshot,
        )
