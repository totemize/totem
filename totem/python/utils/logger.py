import logging
import os
import sys
from datetime import datetime

# Define a singleton pattern to ensure the logger is only set up once
_logger_instance = None

def setup_logger(name='totem', level=logging.DEBUG, console_level=logging.INFO, 
                log_dir=None, log_file=None, suppress_matplotlib=True):
    """
    Set up and configure a logger.
    
    Args:
        name (str): Logger name
        level (int): Overall logging level
        console_level (int): Console logging level
        log_dir (str): Directory for log files, defaults to 'logs' in the project root
        log_file (str): Specific log file to use, defaults to timestamped file
        suppress_matplotlib (bool): Whether to suppress matplotlib font debugging messages
        
    Returns:
        logging.Logger: Configured logger
    """
    global _logger_instance
    
    # Return existing logger if already set up
    if _logger_instance is not None:
        return _logger_instance
    
    # Create logs directory if it doesn't exist and no custom directory provided
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up logging file
    if log_file is None:
        log_file = os.path.join(log_dir, f'totem_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # Configure logger
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    logger.setLevel(level)
    
    # File handler for logging to file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    
    # Console handler for logging to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Suppress matplotlib font debugging messages if requested
    if suppress_matplotlib:
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
    
    _logger_instance = logger
    return logger

def get_logger():
    """
    Get the configured logger instance.
    If logger hasn't been set up, it will be initialized with default settings.
    
    Returns:
        logging.Logger: Logger instance
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = setup_logger()
    
    return _logger_instance

# For backward compatibility with existing code
# This allows existing imports like 'from utils.logger import logger' to continue working
logger = get_logger() 