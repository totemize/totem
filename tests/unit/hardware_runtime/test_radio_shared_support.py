"""Provider-side radio support tests with injected local seams only."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from totem.hardware.builtin.radio.dbus_runtime import DBusRuntime, variant_value
from totem.hardware.builtin.radio.errors import RadioOperationError, RadioTimeoutError
from totem.hardware.builtin.radio.models import RadioService, RadioState


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def test_provider_side_support_names_services_models_and_errors_without_backend_ownership() -> None:
    assert RadioService.NETWORK_MANAGER.destination == "org.freedesktop.NetworkManager"
    assert RadioService.BLUEZ.destination == "org.bluez"
    assert RadioState(available=True, enabled=False).to_json_value() == {"available": True, "enabled": False}
    assert str(RadioOperationError("failed")) == "failed"
    assert isinstance(RadioTimeoutError("timed out"), RadioOperationError)


def test_dbus_runtime_is_injected_and_does_not_contact_or_import_a_system_bus_at_module_import() -> None:
    module = importlib.import_module("totem.hardware.builtin.radio.dbus_runtime")
    calls: list[tuple[object, ...]] = []

    runtime = DBusRuntime(lambda *args, **kwargs: calls.append((args, kwargs)) or ["ok"])

    assert runtime.call("org.example.Service", "/org/example", "org.example.Interface", "Ping") == ["ok"]
    assert calls == [
        (("org.example.Service", "/org/example", "org.example.Interface", "Ping", "", []), {})
    ]
    assert "dbus_next" not in module.__dict__


def test_variant_unwrapping_is_recursive_and_data_only() -> None:
    value = {"nested": [SimpleNamespace(signature="s", value="ok"), {"answer": 42}]}

    assert variant_value(value) == {"nested": ["ok", {"answer": 42}]}
