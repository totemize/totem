"""Deployment-facing CLI composition remains a single local runtime owner."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from totem import __main__ as totem_main
from totem.hardware.runtime.config import ConfigValidationError, RuntimeConfig


pytestmark = pytest.mark.unit


class _Runtime:
    def __init__(self) -> None:
        self.start_calls = 0
        self.close_calls = 0
        self.events = None

    def start(self) -> None:
        self.start_calls += 1

    def close(self) -> None:
        self.close_calls += 1

    def handle(self, _capability_id: str, _binding_id: str) -> object:
        raise RuntimeError("the composition test does not dispatch hardware")


def test_composition_loads_typed_toml_and_translates_legacy_environment_once(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.toml"
    config_path.write_text("[global]\nhost_mode = 'process'\n", encoding="utf-8")
    runtime = _Runtime()
    received = []

    def runtime_factory(config, legacy):
        received.append((config, legacy))
        return runtime

    app = totem_main.compose_application(
        config_path=config_path,
        environ={
            "TOTEM_ALLOW_MOCK_DRIVERS": "true",
            "TOTEM_STORAGE_ROOT": "/tmp/totem-storage",
            "TOTEM_HARDWARE_BUS_URL": "http://127.0.0.1:9010",
        },
        runtime_factory=runtime_factory,
    )

    assert len(received) == 1
    typed_config, legacy = received[0]
    assert typed_config.global_settings["host_mode"] == "process"
    assert legacy.allow_mock_drivers is True
    assert legacy.storage_root == "/tmp/totem-storage"
    assert legacy.bus_url == "http://127.0.0.1:9010"
    assert app.state.hardware_runtime is runtime
    assert app.state.legacy_runtime_config is legacy

    async def exercise_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert runtime.start_calls == 1

    asyncio.run(exercise_lifespan())
    assert runtime.close_calls == 1


def test_injected_runtime_config_takes_precedence_over_the_optional_toml_path(tmp_path: Path) -> None:
    config_path = tmp_path / "runtime.toml"
    config_path.write_text("[global]\nsource = 'toml'\n", encoding="utf-8")
    injected = RuntimeConfig(global_settings={"source": "injected"})
    received = []

    app = totem_main.compose_application(
        config_path=config_path,
        config=injected,
        runtime_factory=lambda config, legacy: received.append((config, legacy)) or _Runtime(),
    )

    assert received[0][0] is injected
    assert app.state.runtime_config is injected


def test_composition_rejects_only_the_affected_invalid_binding(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid-runtime.toml"
    config_path.write_text("[bindings.display]\nhost_mode = 'process'\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as exc_info:
        totem_main.compose_application(config_path=config_path)

    assert exc_info.value.diagnostic.code == "missing_binding_plugin"


def test_totem_command_runs_the_composed_application_without_an_import_string(monkeypatch) -> None:
    app = object()
    calls = []
    monkeypatch.setattr(totem_main, "compose_application", lambda **_kwargs: app)
    monkeypatch.setattr(totem_main.uvicorn, "run", lambda target, **kwargs: calls.append((target, kwargs)))
    monkeypatch.setattr(
        "sys.argv",
        ["totem", "--host", "127.0.0.1", "--port", "9010", "--log-level", "warning"],
    )

    totem_main.main()

    assert calls == [(app, {"host": "127.0.0.1", "port": 9010, "reload": False, "log_level": "warning"})]


def test_start_server_composes_the_same_application_for_the_totem_api_entrypoint(monkeypatch) -> None:
    from totem.api import app as api_app

    application = object()
    calls = []
    monkeypatch.setattr(totem_main, "compose_application", lambda **_kwargs: application)
    monkeypatch.setattr(api_app.uvicorn, "run", lambda target, **kwargs: calls.append((target, kwargs)))

    api_app.start_server(host="127.0.0.1", port=9011, reload=True)

    assert calls == [(application, {"host": "127.0.0.1", "port": 9011, "reload": True})]
