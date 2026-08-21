"""End-to-end manager checks that never touch host hardware."""

import io
import threading

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


def test_display_manager_partial_request_falls_back_on_legacy_driver():
    manager = DisplayManager("mock_eink", allow_mock=True)
    image = Image.new("1", (2, 2), 255)

    manager.display_image(image, refresh_mode="partial")

    assert manager.eink_device.driver.last_image is image
    assert manager._partial_refreshes == 0


def test_display_manager_promotes_partial_refresh_at_safe_cadence():
    manager = DisplayManager(
        "mock_eink",
        allow_mock=True,
        full_refresh_every=3,
    )
    driver = manager.eink_device.driver
    calls = []
    driver.partial_refresh_ready = True
    driver.display_image = lambda image: calls.append(("full", image))
    driver.display_image_partial = lambda image: calls.append(("partial", image))
    images = [Image.new("1", (2, 2), value) for value in (255, 0, 255, 0)]

    for image in images[:3]:
        manager.display_image(image, refresh_mode="partial")
    manager.display_image(images[3], refresh_mode="partial")

    assert [mode for mode, _ in calls] == [
        "partial",
        "partial",
        "full",
        "partial",
    ]
    assert manager._partial_refreshes == 1


def test_display_manager_seeds_unknown_partial_baseline_with_full_refresh():
    manager = DisplayManager("mock_eink", allow_mock=True)
    driver = manager.eink_device.driver
    calls = []
    driver.partial_refresh_ready = False
    driver.display_image = lambda image: calls.append("full")
    driver.display_image_partial = lambda image: calls.append("partial")

    manager.display_image(Image.new("1", (2, 2), 255), "partial")

    assert calls == ["full"]
    assert manager._partial_refreshes == 0


def test_display_manager_full_request_restarts_partial_cadence():
    manager = DisplayManager(
        "mock_eink",
        allow_mock=True,
        full_refresh_every=3,
    )
    driver = manager.eink_device.driver
    calls = []
    driver.partial_refresh_ready = True
    driver.display_image = lambda image: calls.append("full")
    driver.display_image_partial = lambda image: calls.append("partial")
    image = Image.new("1", (2, 2), 255)

    manager.display_image(image, refresh_mode="partial")
    manager.display_image(image, refresh_mode="full")
    manager.display_image(image, refresh_mode="partial")

    assert calls == ["partial", "full", "partial"]
    assert manager._partial_refreshes == 1


@pytest.mark.parametrize("value", (-1, "never", True))
def test_display_manager_rejects_unsafe_full_refresh_cadence(value):
    with pytest.raises(ValueError, match="non-negative integer"):
        DisplayManager(
            "mock_eink",
            allow_mock=True,
            full_refresh_every=value,
        )


def test_display_manager_reads_full_refresh_cadence_from_environment(monkeypatch):
    monkeypatch.setenv("TOTEM_EINK_FULL_REFRESH_EVERY", "7")

    manager = DisplayManager("mock_eink", allow_mock=True)

    assert manager.full_refresh_every == 7


def test_display_manager_defaults_to_no_scheduled_full_refresh():
    manager = DisplayManager("mock_eink", allow_mock=True)

    assert manager.full_refresh_every == 0


def test_display_manager_zero_cadence_never_promotes_partial_refresh():
    manager = DisplayManager(
        "mock_eink",
        allow_mock=True,
        full_refresh_every=0,
    )
    driver = manager.eink_device.driver
    calls = []
    driver.partial_refresh_ready = True
    driver.display_image = lambda image: calls.append("full")
    driver.display_image_partial = lambda image: calls.append("partial")
    image = Image.new("1", (2, 2), 255)

    for _ in range(100):
        manager.display_image(image, "partial")

    assert calls == ["partial"] * 100


def test_display_manager_rejects_unknown_refresh_mode_before_draw():
    manager = DisplayManager("mock_eink", allow_mock=True)

    with pytest.raises(ValueError, match="Unsupported refresh_mode"):
        manager.display_image(Image.new("1", (2, 2), 255), "flashy")

    assert manager.eink_device.driver.last_image is None


def test_display_manager_failed_partial_does_not_advance_cadence():
    manager = DisplayManager("mock_eink", allow_mock=True)
    driver = manager.eink_device.driver
    driver.partial_refresh_ready = True
    driver.display_image_partial = lambda image: (_ for _ in ()).throw(
        TimeoutError("busy")
    )

    with pytest.raises(TimeoutError, match="busy"):
        manager.display_image(Image.new("1", (2, 2), 255), "partial")

    assert manager._partial_refreshes == 0


def test_display_manager_serializes_full_and_partial_draws():
    manager = DisplayManager("mock_eink", allow_mock=True)
    driver = manager.eink_device.driver
    driver.partial_refresh_ready = True
    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    state = {"active": 0, "maximum": 0, "calls": 0}

    def draw(image):
        with state_lock:
            state["active"] += 1
            state["maximum"] = max(state["maximum"], state["active"])
            state["calls"] += 1
        entered.set()
        assert release.wait(timeout=2)
        with state_lock:
            state["active"] -= 1

    driver.display_image = draw
    driver.display_image_partial = draw
    image = Image.new("1", (2, 2), 255)
    first = threading.Thread(target=manager.display_image, args=(image, "partial"))
    second = threading.Thread(target=manager.display_image, args=(image, "full"))

    first.start()
    assert entered.wait(timeout=2)
    second.start()
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert state == {"active": 0, "maximum": 1, "calls": 2}


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
