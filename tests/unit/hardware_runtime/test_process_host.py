"""Fault-injection tests for isolated provider supervision.

All children, clocks, carriers, and broker actions in this file are fakes.
No subprocess, socket, network, or hardware resource is created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import pytest

from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.supervisor import DriverSupervisor, RestartPolicy, SupervisorError


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


@dataclass(frozen=True)
class FakeLease:
    binding_id: str
    generation: int
    owner_token: str


@dataclass
class RecordingBroker:
    actions: List[str] = field(default_factory=list)
    generation: int = 0

    def acquire_many(self, bindings: Tuple[BindingRecord, ...]) -> Tuple[FakeLease, ...]:
        self.generation += 1
        self.actions.append("acquire:{}".format(self.generation))
        return tuple(FakeLease(binding.binding_id, self.generation, "token-{}".format(binding.binding_id)) for binding in bindings)

    def release(self, binding_id: str, generation: int, owner_token: str) -> None:
        assert owner_token == "token-{}".format(binding_id)
        self.actions.append("release:{}:{}".format(binding_id, generation))


@dataclass
class FakeClock:
    sleeps: List[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


@dataclass
class FakeHost:
    ready: bool = True
    terminate_exits: bool = True
    response_generation: Optional[int] = None
    actions: List[str] = field(default_factory=list)
    generation: int = 0
    alive: bool = True

    def await_ready(self, deadline: float) -> Dict[str, object]:
        self.actions.append("ready")
        if not self.ready:
            raise TimeoutError("fake startup timeout")
        return {"type": "host.ready", "generation": self.generation, "binding_ids": ("display",)}

    def invalidate_correlations(self) -> None:
        self.actions.append("invalidate")

    def terminate(self) -> None:
        self.actions.append("terminate")
        if self.terminate_exits:
            self.alive = False

    def kill(self) -> None:
        self.actions.append("kill")
        self.alive = False

    def wait_for_exit(self, deadline: float) -> bool:
        self.actions.append("wait")
        return not self.alive

    def close_carrier(self) -> None:
        self.actions.append("close_carrier")

    def request(self, message: Dict[str, object], attachments=None, deadline=None) -> Dict[str, object]:
        del attachments, deadline
        return {
            "type": "display.frame.write.result",
            "id": message["id"],
            "ok": True,
            "generation": self.response_generation if self.response_generation is not None else self.generation,
        }


def _binding(binding_id: str = "display", grouping: str = "provider") -> BindingRecord:
    provider = SimpleNamespace(
        provider_id="fixture",
        distribution_version="1.0.0",
        manifest=SimpleNamespace(grouping=grouping),
    )
    return BindingRecord("display.frame-sink@1", binding_id, provider, (), ())


def test_groups_by_provider_by_default_and_supports_per_binding_override() -> None:
    supervisor = DriverSupervisor(RecordingBroker(), lambda leases, generation: FakeHost(generation=generation))

    groups = supervisor.groups_for((_binding("first"), _binding("second"), _binding("third", "binding")))

    assert groups == {
        "fixture@1.0.0": ("first", "second"),
        "binding:third": ("third",),
    }


def test_startup_timeout_publishes_no_handle_and_quarantines_when_policy_is_exhausted() -> None:
    broker = RecordingBroker()
    host = FakeHost(ready=False, generation=1)
    supervisor = DriverSupervisor(
        broker,
        lambda leases, generation: host,
        policy=RestartPolicy(max_failures=1),
    )

    with pytest.raises(SupervisorError) as error:
        supervisor.start((_binding(),))

    assert error.value.code == "startup_timeout"
    assert supervisor.handle("display") is None
    assert supervisor.snapshot("fixture@1.0.0").quarantined is True
    assert host.actions == ["ready", "invalidate", "terminate", "wait", "close_carrier"]
    assert broker.actions[-1] == "release:display:1"


def test_hard_hang_confirms_death_and_carrier_close_before_releasing_and_restarting() -> None:
    broker = RecordingBroker()
    first = FakeHost(terminate_exits=False)
    replacement = FakeHost()
    hosts = [first, replacement]
    supervisor = DriverSupervisor(
        broker,
        lambda leases, generation: hosts.pop(0),
        policy=RestartPolicy(retry_delays=(1.0,), max_failures=5),
        sleep=FakeClock().sleep,
    )
    supervisor.start((_binding(),))

    supervisor.recover("fixture@1.0.0", "operation_timeout")

    assert first.actions == ["ready", "invalidate", "terminate", "wait", "kill", "wait", "close_carrier"]
    assert broker.actions == ["acquire:1", "release:display:1", "acquire:2"]
    assert supervisor.snapshot("fixture@1.0.0").generation == 2
    assert supervisor.handle("display") is replacement


def test_stale_generation_result_never_satisfies_a_replacement_request() -> None:
    broker = RecordingBroker()
    host = FakeHost(response_generation=0)
    supervisor = DriverSupervisor(broker, lambda leases, generation: host)
    supervisor.start((_binding(),))

    with pytest.raises(SupervisorError) as error:
        supervisor.request("display", {"type": "display.frame.write", "id": "request-1"})

    assert error.value.code == "stale_generation"
    assert supervisor.handle("display") is None


def test_bounded_backoff_ends_in_actionable_quarantine_without_unbounded_respawn() -> None:
    broker = RecordingBroker()
    clock = FakeClock()
    hosts = [FakeHost() for _ in range(5)]
    supervisor = DriverSupervisor(
        broker,
        lambda leases, generation: hosts.pop(0),
        policy=RestartPolicy(retry_delays=(1.0, 2.0, 4.0, 8.0, 16.0), max_failures=5),
        sleep=clock.sleep,
    )
    supervisor.start((_binding(),))

    for _ in range(5):
        supervisor.recover("fixture@1.0.0", "child_exit")

    status = supervisor.snapshot("fixture@1.0.0")
    assert status.quarantined is True
    assert status.restart_count == 5
    assert status.last_error == "child_exit"
    assert clock.sleeps == [1.0, 2.0, 4.0, 8.0]
    assert supervisor.handle("display") is None
