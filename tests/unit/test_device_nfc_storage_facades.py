"""NFC/storage compatibility facades must delegate through clients only."""

import ast
import inspect
from pathlib import Path
from typing import Any, Callable

import pytest

from totem.devices.nfc.nfc import NFC, NFCDeviceInterface
from totem.devices.storage.device import Storage, StorageDeviceInterface
from totem.devices.storage.files import ConfinedStorage, StorageOptionsError, StoragePathError


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class RecordingClient:
    """Local fake standing in for the canonical hardware client."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        def invoke(*args: object, **kwargs: object) -> object:
            self.calls.append((operation, args, kwargs))
            if operation == "read_card":
                return b"tag"
            if operation == "read_data":
                return b"stored"
            return True

        return invoke


def test_nfc_accepts_an_injected_canonical_client_without_hardware_probe():
    client = RecordingClient()

    facade = NFC("pn532", allow_mock=True, client=client)

    assert facade.client is client
    assert facade.legacy_config == {"driver_name": "pn532", "allow_mock": True}
    assert facade.initialize() is True
    assert facade.read_data() == b"tag"
    assert facade.write_data(b"next") is True
    assert client.calls == [
        ("read_card", (), {}),
        ("write_card", (b"next",), {}),
    ]


def test_storage_accepts_an_injected_canonical_client_without_hardware_probe(tmp_path):
    client = RecordingClient()

    facade = Storage("filesystem", storage_root=tmp_path, client=client)

    assert facade.client is client
    assert facade.legacy_config == {"driver_name": "filesystem", "storage_root": tmp_path}
    assert facade.initialize() is True
    assert facade.read_file("payload.bin") == b"stored"
    assert facade.write_file("payload.bin", b"next", {"append": True}) is True
    assert client.calls == [
        ("read_data", ("payload.bin",), {}),
        ("write_data", ("payload.bin", b"next", {"append": True}), {}),
    ]


def test_close_is_facade_local_and_preserves_shared_client_access():
    client = RecordingClient()
    nfc = NFC(client=client)
    storage = Storage(client=client)

    nfc.close()
    storage.close()

    assert nfc._closed is True
    assert storage._closed is True
    assert nfc.read_data() == b"tag"
    assert storage.read_file("payload.bin") == b"stored"


def test_public_contract_interfaces_and_storage_values_remain_available():
    assert NFCDeviceInterface.__abstractmethods__ == {"init", "read", "write"}
    assert StorageDeviceInterface.__abstractmethods__ == {"init", "read_file", "write_file"}
    assert issubclass(StoragePathError, ValueError)
    assert issubclass(StorageOptionsError, ValueError)
    assert inspect.isclass(ConfinedStorage)


@pytest.mark.parametrize("facade", [NFC, Storage])
def test_wrapper_sources_have_no_provider_registry_transport_or_filesystem_ownership(facade):
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

    assert imports == ["__future__", "abc", "typing", "totem.compat.hardware_client", "totem.devices.contracts"]
    assert not {"_detect_hardware", "_load_driver_by_name"} & names
    assert "DriverRegistry" not in source
    assert "DriverSpec" not in source
    assert "totem.hardware.builtin" not in source
    assert "/dev/" not in source
    assert "importlib" not in source
    assert "subprocess" not in source
    assert "os." not in source
