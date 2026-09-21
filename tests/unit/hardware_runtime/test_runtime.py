"""Local-only composition tests for the public hardware runtime."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Mapping

import pytest

from totem.hardware.capabilities.base import CapabilityUnavailable
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.broker import ResourceBroker
from totem.hardware.runtime.runtime import HardwareRuntime, RuntimeOwnershipError
from totem.hardware.runtime.supervisor import DriverSupervisor, RestartPolicy


@dataclass
class _Host:
    leases: tuple[object, ...]
    generation: int
    fail_ready: bool = False
    fail_request: bool = False
    closed: bool = False

    def await_ready(self, _deadline: float) -> dict[str, object]:
        if self.fail_ready:
            raise TimeoutError("injected startup failure")
        return {
            "type": "host.ready",
            "generation": self.generation,
            "binding_ids": tuple(lease.binding_id for lease in self.leases),
        }

    def request(self, message: Mapping[str, object], **_kwargs: object) -> dict[str, object]:
        if self.fail_request:
            raise TimeoutError("injected operation failure")
        return {"id": message["id"], "binding_id": message["binding_id"], "generation": self.generation}

    def invalidate_correlations(self) -> None:
        return None

    def terminate(self) -> None:
        return None

    def wait_for_exit(self, _deadline: float) -> bool:
        return True

    def kill(self) -> None:
        return None

    def close_carrier(self) -> None:
        self.closed = True

    def health(self) -> dict[str, object]:
        return {"mode": "process"}


def _binding(capability_id: str, binding_id: str) -> BindingRecord:
    record = SimpleNamespace(
        provider_id="test.{}".format(binding_id),
        distribution_version="1.0",
        manifest=SimpleNamespace(grouping="binding", defaults={}),
    )
    return BindingRecord(capability_id, binding_id, record, (), ())


def test_runtime_is_one_eager_owner_with_capability_handles_and_clean_shutdown() -> None:
    display = _binding("display.frame-sink@1", "display")
    wifi = _binding("radio.wifi@1", "wifi")
    hosts: list[_Host] = []
    lifespan = object()

    def make_host(leases: tuple[object, ...], generation: int) -> _Host:
        host = _Host(leases, generation)
        hosts.append(host)
        return host

    runtime = HardwareRuntime(
        (display, wifi),
        broker=ResourceBroker(),
        host_factory=make_host,
        required_binding_ids=("display",),
        lifespan=lifespan,
    )
    with pytest.raises(RuntimeOwnershipError):
        HardwareRuntime((), broker=ResourceBroker(), host_factory=make_host, lifespan=lifespan)

    runtime.start()
    display_handle = runtime.handle("display.frame-sink@1", "display")

    assert runtime.health().ready is True
    assert display_handle.binding_id == "display"
    assert not hasattr(display_handle, "driver")
    assert display_handle.dispatch({"type": "display.frame.write", "id": "one"})["generation"] == 1

    runtime.close()

    assert all(host.closed for host in hosts)
    assert runtime.health().closed is True
    with pytest.raises(CapabilityUnavailable):
        display_handle.dispatch({"type": "display.frame.write", "id": "after-close"})


def test_optional_failure_degrades_but_required_failure_gates_readiness_and_handles() -> None:
    required = _binding("display.frame-sink@1", "required")
    optional = _binding("power.telemetry@1", "optional")

    def optional_failure(leases: tuple[object, ...], generation: int) -> _Host:
        return _Host(leases, generation, fail_ready=leases[0].binding_id == "optional")

    runtime = HardwareRuntime(
        (required, optional),
        broker=ResourceBroker(),
        host_factory=optional_failure,
        required_binding_ids=("required",),
        lifespan=object(),
    )
    runtime.start()

    assert runtime.health().ready is True
    assert runtime.health().degraded is True
    with pytest.raises(CapabilityUnavailable):
        runtime.handle("power.telemetry@1", "optional")
    runtime.close()

    required_failure = HardwareRuntime(
        (required,),
        broker=ResourceBroker(),
        host_factory=lambda leases, generation: _Host(leases, generation, fail_ready=True),
        required_binding_ids=("required",),
        lifespan=object(),
    )
    required_failure.start()
    assert required_failure.health().ready is False
    required_failure.close()


def test_runtime_quarantine_makes_an_existing_handle_unavailable() -> None:
    binding = _binding("display.frame-sink@1", "display")

    runtime = HardwareRuntime(
        (binding,),
        broker=ResourceBroker(),
        host_factory=lambda leases, generation: _Host(leases, generation, fail_request=True),
        lifespan=object(),
        supervisor_factory=lambda broker, host_factory: DriverSupervisor(
            broker,
            host_factory,
            policy=RestartPolicy(max_failures=1),
            sleep=lambda _delay: None,
        ),
    )
    runtime.start()
    handle = runtime.handle("display.frame-sink@1", "display")

    with pytest.raises(CapabilityUnavailable):
        handle.dispatch({"type": "display.frame.write", "id": "timeout"})

    health = runtime.health()
    assert health.bindings["display"].quarantined is True
    assert health.ready is False
    runtime.close()
