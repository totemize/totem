"""Injected-root filesystem implementation for the built-in storage provider."""

import os

from totem.hardware.builtin.storage.files import ConfinedStorage
from totem.logging import logger


class Driver:
    """Preserve legacy filesystem storage behavior without legacy ownership."""

    def __init__(self, root=None):
        configured_root = root or os.environ.get("TOTEM_STORAGE_ROOT", "/var/lib/totem/storage")
        self.storage = ConfinedStorage(configured_root)

    def init(self):
        self.storage.initialize()
        logger.info("Initialized filesystem storage")
        return True

    def read_file(self, file_path):
        return self.storage.read(file_path)

    def write_file(self, file_path, data, options=None):
        return self.storage.write(file_path, data, options)

    def list_files(self, file_path="."):
        return self.storage.list(file_path)

    def delete_file(self, file_path):
        return self.storage.delete(file_path)
