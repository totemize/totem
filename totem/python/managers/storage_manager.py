from devices.nvme.nvme import NVME
from utils.logger import logger
from typing import Optional

class StorageManager:
    def __init__(self, driver_name: Optional[str] = None):
        self.nvme_device = NVME(driver_name)
        self.nvme_device.initialize()

    def write_data(self, file_path: str, data: str) -> bool:
        """
        Write data to a file at the specified path
        
        Args:
            file_path: Path where to write the data
            data: Data to write
            
        Returns:
            bool: True if write was successful
        """
        logger.info(f"Writing data to {file_path}")
        return self.nvme_device.write_file(file_path, data)
        
    def read_data(self, file_path: str) -> str:
        """
        Read data from the specified file path
        
        Args:
            file_path: Path to read from
            
        Returns:
            str: Data read from file
        """
        logger.info(f"Reading data from {file_path}")
        return self.nvme_device.read_file(file_path) 