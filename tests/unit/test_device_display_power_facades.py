"""Legacy display and power device names remain client-only facades."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any, Callable

import pytest

from totem.devices.display import EInk, EInkDeviceInterface
from totem.devices.ups import UPS, UPSDeviceInterface, UPSStatus


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class RecordingClient:
    """A local capability-client seam with no runtime or hardware ownership."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        def invoke(*args: object, **kwargs: object) -> object:
            self.calls.append((operation, args, kwargs))
            if operation == "get_ups_status":
                return UPSStatus("PiSugar2", 75.0, 4.0, -0.2, True)
            return operation

        return invoke


def test_display_constructor_and_operations_only_delegate_to_an_injected_client() -> None:
    client = RecordingClient()
    display = EInk("mock_eink", allow_mock=True, client=client)

    assert display.client is client
    assert display.legacy_config == {"driver_name": "mock_eink", "allow_mock": True}
    assert client.calls == []
    assert display.initialize("full", refresh=True) is True
    assert display.clear_display() is None
    assert display.clear() is None
    assert display.display_image("image") is None
    assert display.display("image") is None
    assert display.display_bytes(b"frame") is None
    assert client.calls == [
        ("clear_screen", (), {}),
        ("clear_screen", (), {}),
        ("display_image", ("image",), {}),
        ("display_image", ("image",), {}),
        ("display_bytes", (b"frame",), {}),
    ]


def test_ups_constructor_lifecycle_and_telemetry_only_use_the_client() -> None:
    client = RecordingClient()
    ups = UPS("pisugar2", client=client)

    assert ups.client is client
    assert ups.legacy_config == {"driver_name": "pisugar2"}
    assert ups.initialize() is True
    assert ups.get_status() == UPSStatus("PiSugar2", 75.0, 4.0, -0.2, True)
    assert client.calls == [("get_ups_status", (), {})]


def test_close_is_facade_local_and_preserves_shared_client_access() -> None:
    client = RecordingClient()
    display = EInk(client=client)
    ups = UPS(client=client)

    display.close()
    ups.close()

    assert display._closed is True
    assert ups._closed is True
    assert ups.get_status().model == "PiSugar2"
    assert client.calls == [("get_ups_status", (), {})]


def test_public_device_imports_and_contract_interfaces_remain_available() -> None:
    assert inspect.isclass(EInk)
    assert inspect.isclass(UPS)
    assert EInkDeviceInterface.__abstractmethods__ == {
        "init",
        "clear",
        "display_image",
        "display_bytes",
    }
    assert UPSDeviceInterface.__abstractmethods__ == {"init", "get_status"}


@pytest.mark.parametrize("facade", [EInk, UPS])
def test_wrapper_sources_have_no_provider_registry_transport_or_hardware_probe(facade) -> None:
    source = Path(inspect.getfile(facade)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    ]
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert imports == ["__future__", "abc", "dataclasses", "typing", "totem.compat.hardware_client", "totem.devices.contracts"]
    assert not {"_detect_hardware", "_load_driver_by_name"} & names
    assert "DriverRegistry" not in source
    assert "DriverSpec" not in source
    assert "/dev/" not in source
    assert "totem.hardware.builtin" not in source

