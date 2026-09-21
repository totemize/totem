"""Explicit lifecycle, health, and event-contract tests.

These are deterministic unit tests: no hardware, process, socket, or network
resource is allocated.
"""

from __future__ import annotations

import pytest

from totem_driver_api.lifecycle import BindingState
from totem.hardware.runtime.events import RuntimeEventStream
from totem.hardware.runtime.lifecycle import (
    BindingLifecycle,
    LifecycleTransitionError,
    RuntimeLifecycle,
    legal_transitions,
)


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def test_every_declared_lifecycle_edge_is_explicit_and_representative_skips_are_safe() -> None:
    """The public graph is traversable only one legal edge at a time."""

    for previous, requested_states in legal_transitions().items():
        for requested in requested_states:
            lifecycle = BindingLifecycle("display", required=True)
            lifecycle.force_state_for_test(previous)
            snapshot = lifecycle.transition(requested)
            assert snapshot.state is requested

    lifecycle = BindingLifecycle("display", required=True)
    before = lifecycle.snapshot()
    with pytest.raises(LifecycleTransitionError) as error:
        lifecycle.transition(BindingState.READY)
    assert error.value.code == "invalid_transition"
    assert error.value.previous is BindingState.DISCOVERED
    assert error.value.requested is BindingState.READY
    assert lifecycle.snapshot() == before


def test_required_optional_and_empty_runtime_readiness_are_reconcileable() -> None:
    runtime = RuntimeLifecycle()
    runtime.add_binding("required-display", required=True, mode="process", process_group="provider")
    runtime.add_binding("optional-power", required=False, mode="process", process_group="provider")
    runtime.transition("required-display", BindingState.MATCHED)
    runtime.transition("required-display", BindingState.BOUND)
    runtime.transition("required-display", BindingState.STARTING)
    runtime.transition("required-display", BindingState.READY)
    runtime.transition("optional-power", BindingState.MATCHED)
    runtime.transition("optional-power", BindingState.BOUND)
    runtime.transition("optional-power", BindingState.STARTING)
    runtime.transition("optional-power", BindingState.FAILED, code="startup_timeout")

    snapshot = runtime.snapshot()
    assert snapshot.ready is True
    assert snapshot.health.value == "degraded"
    assert snapshot.bindings["optional-power"].state is BindingState.FAILED
    assert snapshot.bindings["optional-power"].restart_count == 0
    with pytest.raises(TypeError):
        snapshot.bindings["changed"] = snapshot.bindings["required-display"]

    empty = RuntimeLifecycle()
    assert empty.snapshot().ready is True
    assert empty.close() == empty.close()
    assert empty.snapshot().closed is True


def test_snapshots_and_lossy_events_are_immutable_monotonic_and_redacted() -> None:
    stream = RuntimeEventStream(queue_size=1)
    subscriber = stream.subscribe()
    runtime = RuntimeLifecycle(events=stream)
    runtime.add_binding(
        "display",
        required=True,
        mode="process",
        process_group="fixture@1",
        held_leases=("spi:spi0.0",),
    )
    runtime.transition("display", BindingState.MATCHED)
    runtime.transition("display", BindingState.BOUND)
    runtime.transition("display", BindingState.STARTING, generation=2)
    runtime.transition("display", BindingState.READY)

    events = stream.history()
    assert [event.sequence for event in events] == sorted(event.sequence for event in events)
    assert [event.state for event in events] == [
        BindingState.DISCOVERED,
        BindingState.MATCHED,
        BindingState.BOUND,
        BindingState.STARTING,
        BindingState.READY,
    ]
    assert events[-1].snapshot.generation == 2
    assert events[-1].snapshot.held_leases == ("spi:spi0.0",)
    assert "token" not in repr(events[-1]).lower()
    with pytest.raises(TypeError):
        events[-1].details["changed"] = True
    assert subscriber.get_nowait().sequence == events[-1].sequence


def test_close_orders_hosts_before_runtime_and_is_idempotent() -> None:
    runtime = RuntimeLifecycle()
    runtime.add_binding("display", required=True, mode="process", process_group="provider")
    runtime.transition("display", BindingState.MATCHED)
    runtime.transition("display", BindingState.BOUND)
    runtime.transition("display", BindingState.STARTING)
    runtime.transition("display", BindingState.READY)

    observed = []
    runtime.close(lambda binding: observed.append((binding.binding_id, binding.state)))
    runtime.close(lambda binding: observed.append((binding.binding_id, binding.state)))

    assert observed == [("display", BindingState.READY)]
    assert runtime.snapshot().closed is True
    assert runtime.snapshot().bindings["display"].state is BindingState.CLOSED
