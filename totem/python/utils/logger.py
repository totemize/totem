import logging
import os
import sys
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Set up logging
log_file = os.path.join(log_dir, f'totem_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Configure logger
logger = logging.getLogger('totem')
logger.setLevel(logging.DEBUG)

# File handler for logging to file
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Console handler for logging to console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress matplotlib font debugging messages
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR) 