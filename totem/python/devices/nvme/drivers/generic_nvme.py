import os
import subprocess
import glob
from typing import Optional, List, Dict, Tuple
from devices.nvme.nvme import NVMEDeviceInterface
from utils.logger import logger

class Driver(NVMEDeviceInterface):
    def __init__(self):
        """Initialize the NVMe driver."""
        self.initialized = False
        self.nvme_device = None
        self.partitions = []
        self.mount_points = {}
        self.filesystem_types = {}

    def init(self):
        """Initialize the NVMe drive driver."""
        logger.info("Initializing generic NVMe driver")
        
        # Detect NVMe devices
        self.nvme_device = self._detect_nvme_devices()
        if not self.nvme_device:
            logger.error("No NVMe devices detected")
            return False
            
        logger.info(f"Using NVMe device: {self.nvme_device}")
        
        # Detect partitions
        self.partitions = self._detect_partitions(self.nvme_device)
        if self.partitions:
            logger.info(f"Detected partitions: {', '.join(self.partitions)}")
        else:
            logger.warning("No partitions detected on NVMe device")
        
        # Detect filesystem types
        self.filesystem_types = self._detect_filesystem_types(self.partitions)
        
        # Get mount points
        self.mount_points = self._get_mount_points(self.partitions)
        
        self.initialized = True
        return True
    
    def _detect_nvme_devices(self):
        """Detect NVMe devices in the system."""
        try:
            # Look for nvme devices in /dev
            nvme_devices = []
            for file in os.listdir('/dev/'):
                if file.startswith('nvme') and file.endswith('n1'):
                    nvme_devices.append(os.path.join('/dev', file))
            
            if nvme_devices:
                # Return the first NVMe device found
                return nvme_devices[0]
        except Exception as e:
            logger.error(f"Error detecting NVMe devices: {e}")
        
        return None
    
    def _detect_partitions(self, device):
        """Detect partitions on the specified NVMe device."""
        partitions = []
        try:
            # Look for partition files (e.g., nvme0n1p1, nvme0n1p2, etc.)
            base_name = os.path.basename(device)
            for file in os.listdir('/dev/'):
                if file.startswith(base_name + 'p'):
                    partitions.append(os.path.join('/dev', file))
            
            # Sort partitions numerically
            partitions.sort(key=lambda x: int(x.split('p')[-1]))
        except Exception as e:
            logger.error(f"Error detecting partitions: {e}")
        
        return partitions
    
    def _detect_filesystem_types(self, partitions):
        """Detect filesystem types on each partition."""
        filesystem_types = {}
        
        for partition in partitions:
            try:
                # Try using blkid command first
                try:
                    result = subprocess.run(['blkid', '-o', 'value', '-s', 'TYPE', partition], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0 and result.stdout.strip():
                        filesystem_types[partition] = result.stdout.strip()
                        continue
                except FileNotFoundError:
                    # blkid not available, try alternative methods
                    pass
                
                # Alternative 1: Try using file command
                try:
                    result = subprocess.run(['file', '-sL', partition], 
                                          capture_output=True, text=True, check=False)
                    if result.returncode == 0 and result.stdout:
                        output = result.stdout.lower()
                        if 'ext4' in output:
                            filesystem_types[partition] = 'ext4'
                        elif 'ext3' in output:
                            filesystem_types[partition] = 'ext3'
                        elif 'ext2' in output:
                            filesystem_types[partition] = 'ext2'
                        elif 'fat' in output:
                            if 'fat32' in output:
                                filesystem_types[partition] = 'vfat'
                            else:
                                filesystem_types[partition] = 'fat'
                        elif 'ntfs' in output:
                            filesystem_types[partition] = 'ntfs'
                        continue
                except FileNotFoundError:
                    # file command not available, try next method
                    pass
                
                # Alternative 2: Try mounting with different filesystems
                for fs_type in ['ext4', 'vfat', 'ntfs']:
                    temp_mount = '/tmp/nvme_test_mount'
                    os.makedirs(temp_mount, exist_ok=True)
                    
                    mount_result = subprocess.run(
                        ['mount', '-t', fs_type, partition, temp_mount],
                        capture_output=True, text=True, check=False
                    )
                    
                    if mount_result.returncode == 0:
                        # Successfully mounted, record the filesystem type
                        filesystem_types[partition] = fs_type
                        # Unmount immediately
                        subprocess.run(['umount', temp_mount], check=False)
                        break
                
            except Exception as e:
                logger.error(f"Error detecting filesystem type for {partition}: {e}")
        
        return filesystem_types
    
    def _get_mount_points(self, partitions):
        """Get current mount points for detected partitions."""
        mount_points = {}
        
        try:
            # Get mount information
            result = subprocess.run(['mount'], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                mount_output = result.stdout.splitlines()
                
                for partition in partitions:
                    for line in mount_output:
                        if partition in line:
                            # Extract mount point (format: device on mount_point type fs_type)
                            parts = line.split(' on ')
                            if len(parts) > 1:
                                mount_point = parts[1].split(' ')[0]
                                mount_points[partition] = mount_point
        except Exception as e:
            logger.error(f"Error getting mount points: {e}")
        
        return mount_points
    
    def mount_partition(self, partition, mount_point):
        """Mount a partition to the specified mount point."""
        try:
            # Create mount point directory if it doesn't exist
            os.makedirs(mount_point, exist_ok=True)
            
            # Determine filesystem type
            fs_type = self.filesystem_types.get(partition)
            
            # Mount command
            cmd = ['mount']
            if fs_type:
                cmd.extend(['-t', fs_type])
            cmd.extend([partition, mount_point])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                # Update mount points dictionary
                self.mount_points[partition] = mount_point
                logger.info(f"Successfully mounted {partition} at {mount_point}")
                return True
            else:
                logger.error(f"Failed to mount {partition}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error mounting {partition}: {e}")
            return False
    
    def unmount_partition(self, partition):
        """Unmount a partition."""
        try:
            # Check if partition is mounted
            if partition not in self.mount_points or not self.mount_points[partition]:
                logger.warning(f"{partition} is not mounted")
                return True
            
            # Unmount command
            result = subprocess.run(['umount', partition], capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                # Update mount points dictionary
                mount_point = self.mount_points[partition]
                self.mount_points[partition] = None
                logger.info(f"Successfully unmounted {partition} from {mount_point}")
                return True
            else:
                logger.error(f"Failed to unmount {partition}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error unmounting {partition}: {e}")
            return False
    
    def format_partition(self, partition, fs_type, label=None):
        """Format a partition with the specified filesystem type."""
        try:
            # Unmount partition if it's mounted
            if partition in self.mount_points and self.mount_points[partition]:
                self.unmount_partition(partition)
            
            # Format command based on filesystem type
            if fs_type == 'ext4':
                cmd = ['mkfs.ext4']
                if label:
                    cmd.extend(['-L', label])
                cmd.append(partition)
            elif fs_type == 'fat32' or fs_type == 'vfat':
                cmd = ['mkfs.vfat', '-F', '32']
                if label:
                    cmd.extend(['-n', label])
                cmd.append(partition)
            else:
                logger.error(f"Unsupported filesystem type: {fs_type}")
                return False
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                # Update filesystem type
                self.filesystem_types[partition] = fs_type
                logger.info(f"Successfully formatted {partition} as {fs_type}")
                return True
            else:
                logger.error(f"Failed to format {partition}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error formatting {partition}: {e}")
            return False
    
    def read_file(self, file_path):
        """Read data from a file."""
        try:
            with open(file_path, 'r') as file:
                data = file.read()
            logger.debug(f"Read {len(data)} bytes from {file_path}")
            return data
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""
    
    def write_file(self, file_path, data):
        """Write data to a file."""
        try:
            # Create directory if it doesn't exist
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            
            with open(file_path, 'w') as file:
                file.write(data)
            logger.debug(f"Wrote {len(data)} bytes to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing to file {file_path}: {e}")
            return False
    
    def list_partitions(self):
        """List all detected partitions with their filesystem types and mount points."""
        result = []
        for partition in self.partitions:
            fs_type = self.filesystem_types.get(partition)
            mount_point = self.mount_points.get(partition)
            result.append((partition, fs_type, mount_point))
        return result 