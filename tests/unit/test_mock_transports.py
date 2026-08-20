"""End-to-end manager checks that never touch host hardware."""

import io

from PIL import Image
import pytest

from totem.managers.display_manager import DisplayManager
from totem.managers.network_manager import NetworkManager
from totem.managers.nfc_manager import NFCManager
from totem.managers.storage_manager import StorageManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


def test_display_manager_uses_explicit_mock_transport():
    manager = DisplayManager("mock_eink", allow_mock=True)

    manager.display_text("CI", font_size=12, x=1, y=2)
    manager.display_bytes(b"frame")

    assert manager.eink_device.driver.last_image == b"frame"


def test_display_manager_uses_configured_driver(monkeypatch):
    monkeypatch.setenv("TOTEM_EINK_DRIVER", "mock_eink")

    manager = DisplayManager(allow_mock=True)

    assert manager.driver_name == "mock_eink"
    assert manager.eink_device.driver.is_mock


def test_explicit_display_driver_overrides_environment(monkeypatch):
    monkeypatch.setenv("TOTEM_EINK_DRIVER", "not-a-driver")

    manager = DisplayManager("mock_eink", allow_mock=True)

    assert manager.driver_name == "mock_eink"


def test_display_manager_decodes_encoded_images():
    manager = DisplayManager("mock_eink", allow_mock=True)
    encoded = io.BytesIO()
    Image.new("1", (2, 2), 255).save(encoded, format="PNG")

    manager.display_encoded_image(encoded.getvalue())

    assert isinstance(manager.eink_device.driver.last_image, Image.Image)


def test_nfc_manager_uses_explicit_mock_transport():
    manager = NFCManager("mock_nfc", allow_mock=True)

    manager.write_card("nostr")

    assert manager.read_card() == "nostr"


def test_network_manager_uses_explicit_mock_transport():
    manager = NetworkManager("mock_wifi", allow_mock=True)

    networks = manager.scan_networks()

    assert any(network["SSID"] == "Home_Network" for network in networks)


def test_storage_manager_uses_confined_filesystem_transport(tmp_path):
    manager = StorageManager("filesystem", storage_root=tmp_path)

    manager.write_data("ci/payload.bin", b"payload")

    assert manager.read_data("ci/payload.bin") == b"payload"
