import os
import subprocess
from typing import Optional, List, Dict, Tuple
from devices.nvme.nvme import NVMEDeviceInterface
from utils.logger import logger

class Driver(NVMEDeviceInterface):
    def __init__(self):
        """Initialize the NVMe driver."""
        self.initialized = False
        self.nvme_device = None
        self.nvme_partitions = []
        self.mount_points = {}
        self.detected_filesystems = {}

    def init(self):
        """Initialize the NVMe drive driver."""
        logger.info("Initializing generic NVMe driver")
        
        # Detect NVMe devices
        nvme_devices = self._detect_nvme_devices()
        if not nvme_devices:
            logger.error("No NVMe devices found")
            return False
            
        # Use the first NVMe device found
        self.nvme_device = nvme_devices[0]
        logger.info(f"Using NVMe device: {self.nvme_device}")
        
        # Detect partitions
        self.nvme_partitions = self._detect_partitions(self.nvme_device)
        logger.info(f"Detected partitions: {', '.join(self.nvme_partitions) if self.nvme_partitions else 'None'}")
        
        # Detect filesystem types
        self.detected_filesystems = self._detect_filesystem_types()
        
        # Check if any partitions are already mounted
        self.mount_points = self._get_mount_points()
        
        self.initialized = True
        return True
    
    def _detect_nvme_devices(self) -> List[str]:
        """Detect NVMe devices in the system."""
        nvme_devices = []
        try:
            for file in os.listdir('/dev/'):
                if file.startswith('nvme') and file.endswith('n1'):
                    nvme_devices.append(f"/dev/{file}")
            logger.debug(f"NVMe devices found: {nvme_devices}")
            return nvme_devices
        except Exception as e:
            logger.error(f"Error detecting NVMe devices: {e}")
            return []
    
    def _detect_partitions(self, nvme_device: str) -> List[str]:
        """Detect partitions on the specified NVMe device."""
        partitions = []
        try:
            base_device = os.path.basename(nvme_device)
            for file in os.listdir('/dev/'):
                if file.startswith(base_device + 'p'):
                    partitions.append(f"/dev/{file}")
            return sorted(partitions)
        except Exception as e:
            logger.error(f"Error detecting NVMe partitions: {e}")
            return []
    
    def _detect_filesystem_types(self) -> Dict[str, str]:
        """Detect filesystem types on each partition."""
        filesystem_types = {}
        for partition in self.nvme_partitions:
            try:
                # Use blkid to detect filesystem type
                result = subprocess.run(
                    ['blkid', '-o', 'value', '-s', 'TYPE', partition],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0 and result.stdout.strip():
                    fs_type = result.stdout.strip()
                    filesystem_types[partition] = fs_type
                    logger.info(f"Detected filesystem type on {partition}: {fs_type}")
                else:
                    logger.warning(f"Could not detect filesystem type on {partition}")
            except Exception as e:
                logger.error(f"Error detecting filesystem type for {partition}: {e}")
        
        return filesystem_types
    
    def _get_mount_points(self) -> Dict[str, str]:
        """Get current mount points for the detected partitions."""
        mount_points = {}
        try:
            result = subprocess.run(['mount'], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    for partition in self.nvme_partitions:
                        if partition in line:
                            parts = line.split()
                            mount_point = parts[2]
                            mount_points[partition] = mount_point
                            logger.info(f"Partition {partition} is mounted at {mount_point}")
            return mount_points
        except Exception as e:
            logger.error(f"Error getting mount points: {e}")
            return {}
    
    def mount_partition(self, partition: str, mount_point: str, options: Optional[str] = None) -> bool:
        """
        Mount a partition to the specified mount point.
        
        Args:
            partition: The partition device (e.g., /dev/nvme0n1p1)
            mount_point: Where to mount the partition
            options: Mount options (e.g., "ro,noatime")
            
        Returns:
            bool: True if successful
        """
        if partition in self.mount_points:
            logger.warning(f"Partition {partition} is already mounted at {self.mount_points[partition]}")
            return False
        
        if not os.path.exists(mount_point):
            try:
                os.makedirs(mount_point, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creating mount point directory {mount_point}: {e}")
                return False
        
        cmd = ['mount']
        if options:
            cmd.extend(['-o', options])
        cmd.extend([partition, mount_point])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"Successfully mounted {partition} at {mount_point}")
                self.mount_points[partition] = mount_point
                return True
            else:
                logger.error(f"Failed to mount {partition} at {mount_point}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error mounting {partition}: {e}")
            return False
    
    def unmount_partition(self, partition: str) -> bool:
        """
        Unmount a partition.
        
        Args:
            partition: The partition device to unmount
            
        Returns:
            bool: True if successful
        """
        if partition not in self.mount_points:
            logger.warning(f"Partition {partition} is not mounted")
            return False
        
        try:
            result = subprocess.run(['umount', partition], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"Successfully unmounted {partition}")
                del self.mount_points[partition]
                return True
            else:
                logger.error(f"Failed to unmount {partition}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error unmounting {partition}: {e}")
            return False
    
    def format_partition(self, partition: str, filesystem: str = 'ext4', label: Optional[str] = None) -> bool:
        """
        Format a partition with the specified filesystem.
        
        Args:
            partition: The partition device to format
            filesystem: Filesystem type (e.g., ext4, fat32)
            label: Optional volume label
            
        Returns:
            bool: True if successful
        """
        # Unmount first if mounted
        if partition in self.mount_points:
            if not self.unmount_partition(partition):
                logger.error(f"Cannot format {partition} - failed to unmount")
                return False
        
        cmd = []
        if filesystem.lower() == 'ext4':
            cmd = ['mkfs.ext4']
            if label:
                cmd.extend(['-L', label])
        elif filesystem.lower() in ('fat32', 'vfat'):
            cmd = ['mkfs.vfat', '-F', '32']
            if label:
                cmd.extend(['-n', label])
        else:
            logger.error(f"Unsupported filesystem type: {filesystem}")
            return False
        
        cmd.append(partition)
        
        try:
            logger.warning(f"Formatting {partition} with {filesystem}...")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"Successfully formatted {partition} as {filesystem}")
                # Update filesystem type
                self.detected_filesystems[partition] = filesystem
                return True
            else:
                logger.error(f"Failed to format {partition}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error formatting {partition}: {e}")
            return False
    
    def read_file(self, file_path: str) -> str:
        """
        Read data from a file.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            str: The file contents
        """
        try:
            with open(file_path, 'r') as file:
                data = file.read()
            logger.debug(f"Read {len(data)} bytes from {file_path}")
            return data
        except Exception as e:
            logger.error(f"Error reading from {file_path}: {e}")
            raise
    
    def write_file(self, file_path: str, data: str) -> bool:
        """
        Write data to a file.
        
        Args:
            file_path: Path to the file to write
            data: The data to write
            
        Returns:
            bool: True if successful
        """
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            with open(file_path, 'w') as file:
                file.write(data)
            logger.debug(f"Wrote {len(data)} bytes to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return False
    
    def list_partitions(self) -> List[Tuple[str, Optional[str], Optional[str]]]:
        """
        List all detected partitions with their filesystem types and mount points.
        
        Returns:
            List of tuples containing (partition, filesystem_type, mount_point)
        """
        result = []
        for partition in self.nvme_partitions:
            fs_type = self.detected_filesystems.get(partition)
            mount_point = self.mount_points.get(partition)
            result.append((partition, fs_type, mount_point))
        return result 