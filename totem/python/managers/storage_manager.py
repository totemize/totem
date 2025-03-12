from devices.nvme.nvme import NVME
from utils.logger import logger
from typing import Optional

class StorageManager:
    def __init__(self, driver_name: Optional[str] = None):
        self.nvme_device = NVME(driver_name)
        self.nvme_device.initialize()

    def write_data(self, file_path: str, data: bytes, options: Optional[dict] = None) -> bool:
        """
        Write data to a file at the specified path.
        
        Args:
            file_path (str): Path where to write the data.
            data (bytes): Byte array data to write.
            options (Optional[dict]): A dictionary with write options. Supported options:
                - append (bool): If True, append data to file. Defaults to False.
                - atomic (bool): If True, perform atomic write. Defaults to True.
                - sync (bool): If True, force a filesystem sync after write. Defaults to False.
                - permissions (Optional[int]): File permissions to set after writing. Defaults to None.
                
        Returns:
            bool: True if write was successful.
        """
        logger.info(f"Writing data to {file_path} with options: {options}")
        if options is None:
            options = {}
        default_options = {
            "append": False,
            "atomic": True,
            "sync": False,
            "permissions": None
        }
        config = {**default_options, **options}
        return self.nvme_device.write_file(file_path, data, config)
        
    def read_data(self, file_path: str) -> bytes:
        """
        Read data from the specified file path
        
        Args:
            file_path: Path to read from
            
        Returns:
            bytes: Data read from file
        """
        logger.info(f"Reading data from {file_path}")
        return self.nvme_device.read_file(file_path) 