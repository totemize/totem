"""Single eager owner for a complete capability binding plan."""

from __future__ import annotations

from threading import RLock
from types import MappingProxyType
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from totem_driver_api.lifecycle import BindingState

from totem.hardware.capabilities.base import CapabilityHandle, CapabilityUnavailable

from .bindings import BindingRecord
from .events import RuntimeEventStream
from .health import RuntimeHealth
from .lifecycle import RuntimeLifecycle
from .supervisor import DriverSupervisor, SupervisorError


class RuntimeOwnershipError(RuntimeError):
    """A lifespan attempted to create a second hardware owner."""


class HardwareRuntime:
    """Own one immutable plan, its leases, supervisors, health, and events.

    Construction is entirely dependency injected.  In particular, this module
    does not discover hardware, import a provider, or depend on HTTP transport.
    """

    _owners: Dict[int, "HardwareRuntime"] = {}
    _owner_lock = RLock()

    def __init__(
        self,
        bindings: Iterable[BindingRecord],
        *,
        broker: object,
        host_factory: Callable[[Tuple[object, ...], int], object],
        required_binding_ids: Optional[Iterable[str]] = None,
        lifespan: Optional[object] = None,
        catalog: object = None,
        config: object = None,
        resolver: object = None,
        supervisor_factory: Callable[..., DriverSupervisor] = DriverSupervisor,
    ) -> None:
        plan = tuple(sorted(tuple(bindings), key=lambda binding: binding.binding_id))
        ids = tuple(binding.binding_id for binding in plan)
        if len(ids) != len(set(ids)):
            raise ValueError("runtime binding plan declares duplicate binding identifiers")
        required = frozenset(ids if required_binding_ids is None else required_binding_ids)
        unknown_required = required.difference(ids)
        if unknown_required:
            raise ValueError("required binding is absent from plan: {}".format(sorted(unknown_required)[0]))
        self._lifespan = lifespan if lifespan is not None else self
        self._owner_key = id(self._lifespan)
        with self._owner_lock:
            existing = self._owners.get(self._owner_key)
            if existing is not None:
                raise RuntimeOwnershipError("hardware runtime already owns this lifespan")
            self._owners[self._owner_key] = self
        self.catalog = catalog
        self.config = config
        self.resolver = resolver
        self._plan = plan
        self._bindings = MappingProxyType({binding.binding_id: binding for binding in plan})
        self._capabilities = MappingProxyType({binding.binding_id: binding.capability_id for binding in plan})
        self._required = required
        self._events = RuntimeEventStream()
        self._lifecycle = RuntimeLifecycle(events=self._events)
        self._supervisor = supervisor_factory(broker, host_factory)
        groups = self._supervisor.groups_for(plan)
        self._groups = MappingProxyType(
            {binding_id: group_id for group_id, binding_ids in groups.items() for binding_id in binding_ids}
        )
        self._lock = RLock()
        self._started = False
        self._closed = False
        for binding in self._plan:
            self._lifecycle.add_binding(
                binding.binding_id,
                required=binding.binding_id in self._required,
                process_group=self._groups[binding.binding_id],
            )

    @property
    def bindings(self) -> Mapping[str, BindingRecord]:
        """Return the immutable resolved plan, never mutable runtime state."""

        return self._bindings

    @property
    def events(self) -> RuntimeEventStream:
        """Return the typed ordered lifecycle event stream."""

        return self._events

    def start(self) -> RuntimeHealth:
        """Eagerly start every enabled group in deterministic plan order."""

        with self._lock:
            if self._closed:
                raise RuntimeOwnershipError("hardware runtime is closed")
            if self._started:
                return self.health()
            self._started = True
        for group_id in sorted(set(self._groups.values())):
            group_bindings = tuple(binding for binding in self._plan if self._groups[binding.binding_id] == group_id)
            self._transition_group(group_bindings, BindingState.MATCHED)
            self._transition_group(group_bindings, BindingState.BOUND)
            self._transition_group(group_bindings, BindingState.STARTING)
            try:
                self._supervisor.start(group_bindings)
            except SupervisorError as exc:
                self._transition_group(group_bindings, BindingState.FAILED, code=exc.code)
                continue
            for binding in group_bindings:
                snapshot = self._supervisor.snapshot(self._groups[binding.binding_id])
                self._lifecycle.transition(
                    binding.binding_id,
                    BindingState.READY,
                    generation=snapshot.generation,
                    restart_count=snapshot.restart_count,
                    held_leases=snapshot.held_leases,
                )
        return self.health()

    def health(self) -> RuntimeHealth:
        """Return a typed redacted health projection for application consumers."""

        return RuntimeHealth.from_snapshot(self._lifecycle.snapshot(), self._capabilities)

    def handle(self, capability_id: str, binding_id: str) -> CapabilityHandle:
        """Publish a family handle only for an eagerly ready binding identity."""

        binding = self._bindings.get(binding_id)
        if binding is None or binding.capability_id != capability_id:
            raise CapabilityUnavailable("capability binding is unavailable")
        snapshot = self._lifecycle.snapshot().bindings[binding_id]
        if self._closed or snapshot.state is not BindingState.READY or snapshot.quarantined or snapshot.contaminated:
            raise CapabilityUnavailable("capability binding is unavailable")
        return CapabilityHandle(capability_id, binding_id, self._dispatch)

    def default_binding_id(self, message_type: str) -> Optional[str]:
        """Select the sole ready binding for a domain without a type registry.

        Ambiguous domains deliberately require the outward client to supply an
        explicit binding.  This keeps routing in resolved plan metadata rather
        than a central provider/capability switch.
        """

        if not isinstance(message_type, str) or "." not in message_type:
            return None
        domain = message_type.split(".", 1)[0]
        candidates = [
            binding_id
            for binding_id, binding in self._bindings.items()
            if domain in binding.capability_id.split("@", 1)[0].split(".")
            and self._lifecycle.snapshot().bindings[binding_id].state is BindingState.READY
        ]
        return candidates[0] if len(candidates) == 1 else None

    def close(self) -> RuntimeHealth:
        """Close every supervisor before releasing the lifespan owner guard."""

        with self._lock:
            if self._closed:
                return self.health()
            contaminated = tuple(
                snapshot.binding_id
                for snapshot in self._lifecycle.snapshot().bindings.values()
                if snapshot.contaminated
            )
            if contaminated:
                raise RuntimeOwnershipError("controlled restart required for contaminated binding")
            self._supervisor.close()
            self._lifecycle.close()
            self._closed = True
        with self._owner_lock:
            if self._owners.get(self._owner_key) is self:
                del self._owners[self._owner_key]
        return self.health()

    def _dispatch(self, capability_id: str, binding_id: str, message: Mapping[str, object]) -> Mapping[str, object]:
        binding = self._bindings.get(binding_id)
        snapshot = self._lifecycle.snapshot().bindings.get(binding_id)
        if (
            self._closed
            or binding is None
            or binding.capability_id != capability_id
            or snapshot is None
            or snapshot.state is not BindingState.READY
            or snapshot.quarantined
            or snapshot.contaminated
        ):
            raise CapabilityUnavailable("capability binding is unavailable")
        request = dict(message)
        request["binding_id"] = binding_id
        try:
            return self._supervisor.request(binding_id, request)
        except SupervisorError as exc:
            self._record_supervisor_failure(binding_id, exc.code)
            raise CapabilityUnavailable(exc.code) from exc

    def _record_supervisor_failure(self, binding_id: str, code: str) -> None:
        """Mirror supervisor fault containment into the typed health projection."""

        group_id = self._groups[binding_id]
        supervisor_snapshot = self._supervisor.snapshot(group_id)
        for grouped_binding_id in supervisor_snapshot.binding_ids:
            current = self._lifecycle.snapshot().bindings[grouped_binding_id].state
            if supervisor_snapshot.contaminated and current is not BindingState.CONTAMINATED:
                self._lifecycle.transition(grouped_binding_id, BindingState.CONTAMINATED, code=code)
                continue
            if current is BindingState.READY:
                self._lifecycle.transition(grouped_binding_id, BindingState.FAILED, code=code)
                current = BindingState.FAILED
            if supervisor_snapshot.quarantined and current is BindingState.FAILED:
                self._lifecycle.transition(grouped_binding_id, BindingState.QUARANTINED, code=code)

    def _transition_group(self, bindings: Sequence[BindingRecord], state: BindingState, *, code: Optional[str] = None) -> None:
        for binding in bindings:
            self._lifecycle.transition(binding.binding_id, state, code=code)
