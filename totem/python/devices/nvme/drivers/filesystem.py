import os
from devices.nvme.nvme import NVMEDeviceInterface
from utils.logger import logger

class Driver(NVMEDeviceInterface):
    def init(self):
        """Initialize the filesystem driver."""
        logger.info("Initializing filesystem storage driver")
        # No special initialization needed for basic file operations
        pass

    def read_file(self, file_path):
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

    def write_file(self, file_path, data):
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