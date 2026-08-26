"""Generation-aware external driver supervision and bounded recovery."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple

from .bindings import BindingRecord


@dataclass(frozen=True)
class RestartPolicy:
    """Typed safety defaults; fleet performance budgets remain a deferred gate."""

    startup_deadline: float = 10.0
    cancellation_grace: float = 0.5
    terminate_grace: float = 2.0
    retry_delays: Tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)
    max_failures: int = 5
    failure_window: float = 600.0

    def __post_init__(self) -> None:
        if self.startup_deadline <= 0 or self.cancellation_grace < 0 or self.terminate_grace <= 0:
            raise ValueError("supervisor deadlines must be positive")
        if not self.retry_delays or any(delay <= 0 for delay in self.retry_delays):
            raise ValueError("retry delays must be positive")
        if self.max_failures < 1 or self.failure_window <= 0:
            raise ValueError("failure policy must be bounded and positive")

    def delay_for(self, failure_count: int) -> float:
        if failure_count < 1:
            raise ValueError("failure count must be positive")
        return self.retry_delays[min(failure_count - 1, len(self.retry_delays) - 1)]


class SupervisorError(RuntimeError):
    """Stable failure code without a provider traceback or secret value."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        self.code = code
        super().__init__(message or code.replace("_", " "))


@dataclass(frozen=True)
class SupervisorSnapshot:
    group_id: str
    binding_ids: Tuple[str, ...]
    generation: int
    restart_count: int
    quarantined: bool
    last_error: Optional[str]
    ready: bool


@dataclass
class _GroupState:
    group_id: str
    bindings: Tuple[BindingRecord, ...]
    leases: Tuple[object, ...] = ()
    host: object = None
    generation: int = 0
    restart_count: int = 0
    quarantined: bool = False
    last_error: Optional[str] = None


class DriverSupervisor:
    """Contain child failure without provider imports in the daemon process.

    ``host_factory`` is deliberately injected.  The production process host
    owns ``subprocess.Popen`` and the framed carrier, while these mechanics
    can be fully fault-injected with local Popen-shaped fakes.
    """

    def __init__(
        self,
        broker: object,
        host_factory: Callable[[Tuple[object, ...], int], object],
        *,
        policy: Optional[RestartPolicy] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._broker = broker
        self._host_factory = host_factory
        self._policy = policy or RestartPolicy()
        self._sleep = sleep
        self._groups: Dict[str, _GroupState] = {}
        self._routes: Dict[str, _GroupState] = {}

    def groups_for(self, bindings: Sequence[BindingRecord]) -> Mapping[str, Tuple[str, ...]]:
        """Return deterministic provider-default or explicit per-binding groups."""

        groups: Dict[str, list[str]] = {}
        for binding in bindings:
            group_id = self._group_id(binding)
            groups.setdefault(group_id, []).append(binding.binding_id)
        return {group_id: tuple(binding_ids) for group_id, binding_ids in sorted(groups.items())}

    def start(self, bindings: Sequence[BindingRecord]) -> None:
        """Acquire each group and publish routes only after its ready handshake."""

        by_group: Dict[str, list[BindingRecord]] = {}
        for binding in bindings:
            by_group.setdefault(self._group_id(binding), []).append(binding)
        for group_id, members in sorted(by_group.items()):
            state = _GroupState(group_id=group_id, bindings=tuple(members))
            self._groups[group_id] = state
            self._start_group(state)

    def handle(self, binding_id: str) -> object:
        """Return the ready host for a binding, otherwise no published handle."""

        state = self._routes.get(binding_id)
        return None if state is None else state.host

    def snapshot(self, group_id: str) -> SupervisorSnapshot:
        state = self._groups[group_id]
        return SupervisorSnapshot(
            group_id=state.group_id,
            binding_ids=tuple(binding.binding_id for binding in state.bindings),
            generation=state.generation,
            restart_count=state.restart_count,
            quarantined=state.quarantined,
            last_error=state.last_error,
            ready=state.host is not None and not state.quarantined,
        )

    def request(
        self,
        binding_id: str,
        message: Mapping[str, object],
        attachments: Optional[Mapping[str, object]] = None,
        deadline: Optional[float] = None,
    ) -> Mapping[str, object]:
        """Route only to the currently ready generation and reject stale results."""

        state = self._routes.get(binding_id)
        if state is None or state.host is None or state.quarantined:
            raise SupervisorError("host_unavailable")
        try:
            result = state.host.request(dict(message), attachments=attachments, deadline=deadline)
        except TimeoutError:
            self._fail_group(state, "operation_timeout")
            raise SupervisorError("operation_timeout")
        except Exception:
            self._fail_group(state, "host_exchange_failed")
            raise SupervisorError("host_exchange_failed")
        if not isinstance(result, Mapping) or result.get("generation") != state.generation:
            self._fail_group(state, "stale_generation")
            raise SupervisorError("stale_generation")
        return result

    def recover(self, group_id: str, reason: str) -> None:
        """Recover a crash/hang in the sole safety order that releases leases."""

        state = self._groups[group_id]
        self._fail_group(state, reason)

    def controlled_restart(self, group_id: str) -> None:
        """An explicit operator/daemon restart is the only quarantine reset."""

        state = self._groups[group_id]
        if state.host is not None:
            self._stop_and_release(state)
        state.quarantined = False
        state.restart_count = 0
        state.last_error = None
        self._start_group(state)

    def close(self) -> None:
        """Close every group without replacing it."""

        for state in tuple(self._groups.values()):
            if state.host is not None:
                self._stop_and_release(state)

    def _start_group(self, state: _GroupState) -> None:
        if state.quarantined:
            raise SupervisorError("quarantined")
        try:
            leases = tuple(self._broker.acquire_many(state.bindings))
            generations = {getattr(lease, "generation", None) for lease in leases}
            if len(generations) != 1 or None in generations:
                raise SupervisorError("invalid_lease_generation")
            generation = next(iter(generations))
            host = self._host_factory(leases, generation)
            ready = host.await_ready(self._policy.startup_deadline)
            expected_bindings = tuple(sorted(binding.binding_id for binding in state.bindings))
            actual_bindings = tuple(sorted(ready.get("binding_ids", ()))) if isinstance(ready, Mapping) else ()
            if (
                not isinstance(ready, Mapping)
                or ready.get("type") != "host.ready"
                or ready.get("generation") != generation
                or actual_bindings != expected_bindings
            ):
                raise SupervisorError("ready_mismatch")
        except TimeoutError:
            if "host" in locals():
                state.host = host
                state.leases = leases
                state.generation = generation
                self._stop_and_release(state)
            self._record_failure(state, "startup_timeout", restart=False)
            raise SupervisorError("startup_timeout")
        except SupervisorError:
            if "host" in locals():
                state.host = host
                state.leases = leases
                state.generation = generation
                self._stop_and_release(state)
            self._record_failure(state, "startup_failed", restart=False)
            raise
        except Exception as exc:
            if "host" in locals():
                state.host = host
                state.leases = leases
                state.generation = generation
                self._stop_and_release(state)
            self._record_failure(state, "startup_failed", restart=False)
            raise SupervisorError("startup_failed") from exc
        state.leases = leases
        state.host = host
        state.generation = generation
        state.last_error = None
        for binding in state.bindings:
            self._routes[binding.binding_id] = state

    def _fail_group(self, state: _GroupState, reason: str) -> None:
        if state.host is not None:
            self._stop_and_release(state)
        self._record_failure(state, reason, restart=True)

    def _record_failure(self, state: _GroupState, reason: str, *, restart: bool) -> None:
        state.restart_count += 1
        state.last_error = reason
        if state.restart_count >= self._policy.max_failures:
            state.quarantined = True
            return
        if restart:
            self._sleep(self._policy.delay_for(state.restart_count))
            self._start_group(state)

    def _stop_and_release(self, state: _GroupState) -> None:
        """Invalidate → terminate/kill → wait → close carrier → release leases."""

        host = state.host
        if host is None:
            return
        for binding in state.bindings:
            self._routes.pop(binding.binding_id, None)
        host.invalidate_correlations()
        host.terminate()
        dead = host.wait_for_exit(self._policy.terminate_grace)
        if not dead:
            host.kill()
            dead = host.wait_for_exit(self._policy.terminate_grace)
        if not dead:
            # The carrier and leases remain live; a presumed death can never
            # release a physical claim or authorize a replacement owner.
            raise SupervisorError("child_death_unconfirmed")
        host.close_carrier()
        for lease in state.leases:
            self._broker.release(lease.binding_id, lease.generation, lease.owner_token)
        state.host = None
        state.leases = ()

    @staticmethod
    def _group_id(binding: BindingRecord) -> str:
        record = binding.provider_record
        grouping = getattr(getattr(record, "manifest", None), "grouping", "provider")
        if grouping == "binding":
            return "binding:{}".format(binding.binding_id)
        return "{}@{}".format(record.provider_id, record.distribution_version)
