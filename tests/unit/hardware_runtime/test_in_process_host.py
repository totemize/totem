"""Contract tests for the explicit, cooperative in-process driver host."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from totem.hardware.hosts.in_process import InProcessDriverHost, InProcessHostError
from totem.hardware.runtime.bindings import BindingRecord
from totem.hardware.runtime.config import BindingConfig, PluginConfig, RuntimeConfig
from totem.hardware.runtime.supervisor import DriverSupervisor, RestartPolicy, SupervisorError


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


@dataclass(frozen=True)
class FakeLease:
    binding_id: str
    generation: int
    owner_token: str


@dataclass
class RecordingBroker:
    actions: List[str]

    def acquire_many(self, bindings: Tuple[BindingRecord, ...]) -> Tuple[FakeLease, ...]:
        self.actions.append("acquire")
        return tuple(FakeLease(binding.binding_id, 1, "token") for binding in bindings)

    def release(self, binding_id: str, generation: int, owner_token: str) -> None:
        self.actions.append("release:{}:{}".format(binding_id, generation))


def _binding(binding_id: str = "display") -> BindingRecord:
    provider = SimpleNamespace(
        provider_id="fixture.display",
        distribution_version="1.0.0",
        entry_point_value="tests.fixture:provider",
        manifest=SimpleNamespace(grouping="provider"),
    )
    return BindingRecord("display.frame-sink@1", binding_id, provider, (), ())


def _request(request_id: str = "request-1") -> Dict[str, object]:
    return {
        "type": "display.frame.write",
        "id": request_id,
        "binding_id": "display",
        "frame": {"attachment_id": "frame", "width": 1, "height": 1, "pixel_format": "mono"},
    }


class CooperativeProvider:
    def write_frame(self, request: object, *, cancel_event: Optional[threading.Event] = None) -> Dict[str, object]:
        assert cancel_event is not None
        cancel_event.wait(1.0)
        return {"attachment_id": getattr(request, "attachment_id"), "accepted": False}


class UncooperativeProvider:
    def __init__(self) -> None:
        self.release = threading.Event()

    def write_frame(self, request: object, *, cancel_event: Optional[threading.Event] = None) -> Dict[str, object]:
        del cancel_event
        self.release.wait(1.0)
        return {"attachment_id": getattr(request, "attachment_id"), "accepted": True}


def test_cooperative_deadline_signals_cancellation_and_returns_ready_for_follow_up() -> None:
    host = InProcessDriverHost((_binding(),), CooperativeProvider(), generation=1, cancellation_grace=0.05)

    with pytest.raises(InProcessHostError, match="deadline_exceeded"):
        host.request(_request(), attachments={"frame": b"x"}, deadline=0.001)

    assert host.health()["state"] == "READY"
    assert host.health()["cancellations"] == 1
    assert host.request(_request("request-2"), attachments={"frame": b"x"})["ok"] is True


def test_uncooperative_deadline_contaminates_and_supervisor_retains_leases_until_restart() -> None:
    provider = UncooperativeProvider()
    broker = RecordingBroker([])
    supervisor = DriverSupervisor(
        broker,
        lambda leases, generation: InProcessDriverHost(leases, provider, generation=generation, cancellation_grace=0.001),
        policy=RestartPolicy(max_failures=1),
    )
    supervisor.start((_binding(),))

    with pytest.raises(SupervisorError, match="contaminated"):
        supervisor.request("display", _request(), attachments={"frame": b"x"}, deadline=0.001)

    status = supervisor.snapshot("fixture.display@1.0.0")
    assert status.contaminated is True
    assert status.restart_required is True
    assert status.held_leases == ("display",)
    assert status.live_invocation is True
    assert broker.actions == ["acquire"]
    with pytest.raises(SupervisorError) as unavailable:
        supervisor.request("display", _request("request-2"), attachments={"frame": b"x"})
    assert unavailable.value.code == "host_unavailable"
    supervisor.close()
    assert broker.actions == ["acquire"]
    provider.release.set()


def test_host_mode_selection_is_binding_then_plugin_then_global_then_manifest_default() -> None:
    manifest = SimpleNamespace(provider_id="fixture.display", defaults={"host_mode": "process"})
    runtime = RuntimeConfig(
        global_settings={"host_mode": "in_process"},
        plugins=(PluginConfig("fixture.display", {"host_mode": "process"}),),
        bindings=(BindingConfig("display", "fixture.display", {"host_mode": "in_process"}),),
    )

    assert DriverSupervisor.host_mode_for(_binding(), runtime, manifest) == "in_process"
    assert DriverSupervisor.host_mode_for(_binding("other"), runtime, manifest) == "process"
    assert DriverSupervisor.host_mode_for(_binding("unconfigured"), RuntimeConfig(), manifest) == "process"
