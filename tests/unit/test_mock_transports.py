"""Manager compatibility checks with explicit local client fakes only."""

from __future__ import annotations

from typing import Any

import pytest

from totem.managers.display_manager import DisplayManager
from totem.managers.network_manager import NetworkManager
from totem.managers.nfc_manager import NFCManager
from totem.managers.storage_manager import StorageManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


class LocalFakeClient:
    """In-memory client seam that owns neither a runtime nor a driver."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.storage: dict[str, bytes] = {}
        self.card = ""

    def _record(self, operation: str, *args: object) -> None:
        self.calls.append((operation, args))

    def display_text(self, *args: object) -> None:
        self._record("display_text", *args)

    def display_bytes(self, *args: object) -> None:
        self._record("display_bytes", *args)

    def display_encoded_image(self, *args: object) -> None:
        self._record("display_encoded_image", *args)

    def write_card(self, data: str) -> None:
        self._record("write_card", data)
        self.card = data

    def read_card(self) -> str:
        self._record("read_card")
        return self.card

    def scan_wifi_networks(self, *args: object) -> list[dict[str, Any]]:
        self._record("scan_wifi_networks", *args)
        return [{"ssid": "Home_Network", "signal_percent": 100}]

    def write_data(self, file_path: str, data: bytes, options: dict) -> bool:
        self._record("write_data", file_path, data, options)
        self.storage[file_path] = data
        return True

    def read_data(self, file_path: str) -> bytes:
        self._record("read_data", file_path)
        return self.storage[file_path]


def test_display_manager_uses_explicit_mock_transport():
    client = LocalFakeClient()
    manager = DisplayManager("mock_eink", allow_mock=True, client=client)

    manager.display_text("CI", font_size=12, x=1, y=2)
    manager.display_bytes(b"frame")

    assert manager.legacy_config == {"driver_name": "mock_eink", "allow_mock": True}
    assert client.calls == [
        ("display_text", ("CI", 12, 1, 2, None)),
        ("display_bytes", (b"frame",)),
    ]


def test_display_manager_does_not_select_a_driver_from_environment(monkeypatch):
    monkeypatch.setenv("TOTEM_EINK_DRIVER", "mock_eink")

    manager = DisplayManager(allow_mock=True, client=LocalFakeClient())

    assert manager.legacy_config == {"driver_name": None, "allow_mock": True}


def test_explicit_display_driver_remains_outward_boundary_configuration(monkeypatch):
    monkeypatch.setenv("TOTEM_EINK_DRIVER", "not-a-driver")

    manager = DisplayManager("mock_eink", allow_mock=True, client=LocalFakeClient())

    assert manager.legacy_config["driver_name"] == "mock_eink"


def test_display_manager_delegates_encoded_images_to_the_local_client():
    client = LocalFakeClient()
    manager = DisplayManager("mock_eink", allow_mock=True, client=client)

    manager.display_encoded_image(b"encoded-frame")

    assert client.calls == [("display_encoded_image", (b"encoded-frame",))]


def test_nfc_manager_uses_explicit_mock_transport():
    client = LocalFakeClient()
    manager = NFCManager("mock_nfc", allow_mock=True, client=client)

    manager.write_card("nostr")

    assert manager.read_card() == "nostr"
    assert client.calls == [("write_card", ("nostr",)), ("read_card", ())]


def test_network_manager_uses_explicit_mock_transport():
    client = LocalFakeClient()
    manager = NetworkManager("mock_wifi", allow_mock=True, client=client)

    networks = manager.scan_networks()

    assert networks == [{"SSID": "Home_Network", "Signal": "100"}]
    assert client.calls == [("scan_wifi_networks", ())]


def test_storage_manager_uses_confined_filesystem_transport(tmp_path):
    client = LocalFakeClient()
    manager = StorageManager("filesystem", storage_root=tmp_path, client=client)

    manager.write_data("ci/payload.bin", b"payload")

    assert manager.read_data("ci/payload.bin") == b"payload"
    assert client.calls == [
        ("write_data", ("ci/payload.bin", b"payload", {})),
        ("read_data", ("ci/payload.bin",)),
    ]
