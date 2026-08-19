import os

import pytest

from totem.devices.storage.drivers.filesystem import Driver as FilesystemDriver
from totem.devices.storage.drivers.generic_nvme import Driver as GenericNVMeDriver
from totem.devices.storage.files import StorageOptionsError, StoragePathError
from totem.managers.storage_manager import StorageManager


pytestmark = [pytest.mark.unit, pytest.mark.mock_transport]


@pytest.fixture(params=(FilesystemDriver, GenericNVMeDriver))
def storage_driver(request, tmp_path):
    driver = request.param(root=tmp_path)
    if isinstance(driver, GenericNVMeDriver):
        driver.storage.initialize()
    else:
        assert driver.init() is True
    return driver, tmp_path


def test_binary_round_trip(storage_driver):
    driver, root = storage_driver
    payload = bytes(range(256)) + b"\x00\xff\n"

    assert driver.write_file("nested/blob.bin", payload) is True
    assert driver.read_file("nested/blob.bin") == payload
    assert (root / "nested" / "blob.bin").read_bytes() == payload


def test_append_has_identical_semantics(storage_driver):
    driver, _ = storage_driver
    driver.write_file("events.bin", b"first")

    driver.write_file("events.bin", b"-second", {"append": True})

    assert driver.read_file("events.bin") == b"first-second"


@pytest.mark.parametrize("requested", ("../escape", "nested/../../escape"))
def test_rejects_traversal(storage_driver, requested):
    driver, _ = storage_driver

    with pytest.raises(StoragePathError):
        driver.write_file(requested, b"nope")


def test_rejects_absolute_paths(storage_driver, tmp_path):
    driver, _ = storage_driver

    with pytest.raises(StoragePathError):
        driver.read_file(str(tmp_path / "absolute"))


def test_rejects_symlink_escape(storage_driver, tmp_path):
    driver, root = storage_driver
    outside = tmp_path.parent / "outside-storage"
    outside.mkdir(exist_ok=True)
    (root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(StoragePathError):
        driver.write_file("escape/file.bin", b"nope")


def test_rejects_text_and_unknown_options(storage_driver):
    driver, _ = storage_driver

    with pytest.raises(TypeError):
        driver.write_file("text.txt", "not bytes")
    with pytest.raises(StorageOptionsError):
        driver.write_file("data.bin", b"data", {"made_up": True})


def test_permissions_and_non_atomic_write(storage_driver):
    driver, root = storage_driver

    driver.write_file(
        "private.bin",
        bytearray(b"secret"),
        {"atomic": False, "sync": True, "permissions": 0o600},
    )

    path = root / "private.bin"
    assert path.read_bytes() == b"secret"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_manager_accepts_explicit_storage_root(tmp_path):
    manager = StorageManager("filesystem", storage_root=tmp_path)

    assert manager.write_data("managed.bin", b"managed") is True
    assert manager.read_data("managed.bin") == b"managed"
