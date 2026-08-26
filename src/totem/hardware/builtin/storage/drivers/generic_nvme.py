"""Generic NVMe storage behavior owned by the built-in storage provider."""

import glob
import os
import subprocess

from totem.hardware.builtin.storage.files import ConfinedStorage
from totem.logging import logger


class Driver:
    """Retain legacy NVMe discovery and maintenance operations behind an injected root."""

    def __init__(self, root=None):
        self.initialized = False
        self.nvme_device = None
        self.partitions = []
        self.mount_points = {}
        self.filesystem_types = {}
        configured_root = root or os.environ.get("TOTEM_STORAGE_ROOT", "/mnt/nvme")
        self.storage = ConfinedStorage(configured_root)

    def init(self):
        logger.info("Initializing generic NVMe driver")
        self.nvme_device = self._detect_nvme_devices()
        if not self.nvme_device:
            logger.error("No NVMe devices detected")
            return False
        self.partitions = self._detect_partitions(self.nvme_device)
        self.filesystem_types = self._detect_filesystem_types(self.partitions)
        self.mount_points = self._get_mount_points(self.partitions)
        self.initialized = True
        self.storage.initialize()
        return True

    def _detect_nvme_devices(self):
        try:
            devices = sorted(glob.glob("/dev/nvme*n1"))
            return devices[0] if devices else None
        except OSError as exc:
            logger.error("Error detecting NVMe devices: %s", exc)
            return None

    def _detect_partitions(self, device):
        try:
            return sorted(glob.glob("{}p*".format(device)), key=lambda path: int(path.rsplit("p", 1)[1]))
        except (OSError, ValueError) as exc:
            logger.error("Error detecting NVMe partitions: %s", exc)
            return []

    def _detect_filesystem_types(self, partitions):
        filesystem_types = {}
        for partition in partitions:
            try:
                result = subprocess.run(
                    ["blkid", "-o", "value", "-s", "TYPE", partition],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    filesystem_types[partition] = result.stdout.strip()
            except OSError as exc:
                logger.error("Error detecting filesystem type: %s", exc)
        return filesystem_types

    def _get_mount_points(self, partitions):
        mount_points = {}
        try:
            result = subprocess.run(["mount"], capture_output=True, text=True, check=False)
        except OSError as exc:
            logger.error("Error reading mount points: %s", exc)
            return mount_points
        if result.returncode != 0:
            return mount_points
        for partition in partitions:
            for line in result.stdout.splitlines():
                if partition in line and " on " in line:
                    mount_points[partition] = line.split(" on ", 1)[1].split(" ", 1)[0]
                    break
        return mount_points

    def mount_partition(self, partition, mount_point):
        try:
            os.makedirs(mount_point, exist_ok=True)
            command = ["mount"]
            if self.filesystem_types.get(partition):
                command.extend(["-t", self.filesystem_types[partition]])
            command.extend([partition, mount_point])
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self.mount_points[partition] = mount_point
                return True
        except OSError as exc:
            logger.error("Error mounting NVMe partition: %s", exc)
        return False

    def unmount_partition(self, partition):
        if not self.mount_points.get(partition):
            return True
        try:
            result = subprocess.run(["umount", partition], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self.mount_points[partition] = None
                return True
        except OSError as exc:
            logger.error("Error unmounting NVMe partition: %s", exc)
        return False

    def format_partition(self, partition, fs_type, label=None):
        if self.mount_points.get(partition):
            self.unmount_partition(partition)
        commands = {
            "ext4": ["mkfs.ext4"],
            "fat32": ["mkfs.vfat", "-F", "32"],
            "vfat": ["mkfs.vfat", "-F", "32"],
        }
        command = commands.get(fs_type)
        if command is None:
            return False
        if label:
            command.extend(["-L" if fs_type == "ext4" else "-n", label])
        try:
            result = subprocess.run(command + [partition], capture_output=True, text=True, check=False)
        except OSError as exc:
            logger.error("Error formatting NVMe partition: %s", exc)
            return False
        if result.returncode == 0:
            self.filesystem_types[partition] = fs_type
            return True
        return False

    def read_file(self, file_path):
        return self.storage.read(file_path)

    def write_file(self, file_path, data, options=None):
        return self.storage.write(file_path, data, options)

    def list_files(self, file_path="."):
        return self.storage.list(file_path)

    def delete_file(self, file_path):
        return self.storage.delete(file_path)

    def list_partitions(self):
        return [
            (partition, self.filesystem_types.get(partition), self.mount_points.get(partition))
            for partition in self.partitions
        ]
