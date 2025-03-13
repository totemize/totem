#!/usr/bin/env python3
import os, sys, subprocess, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gpio-check")

# Check user
logger.info(f"User: {subprocess.check_output(['whoami']).decode().strip()}")

# Check groups
logger.info(f"Groups: {subprocess.check_output(['groups']).decode().strip()}")

# Check GPIO devices
for dev in ["/dev/gpiochip0", "/dev/spidev0.0"]:
    if os.path.exists(dev):
        stat = os.stat(dev)
        logger.info(f"{dev}: mode={oct(stat.st_mode)}")
        logger.info(f"{dev} access: r={os.access(dev,os.R_OK)} w={os.access(dev,os.W_OK)}")
    else:
        logger.info(f"{dev} does not exist")

# Check for processes using GPIO
try:
    result = subprocess.run(["lsof", "/dev/gpiochip0"], capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("Processes using /dev/gpiochip0:")
        for line in result.stdout.strip().split('\n'):
            logger.info(line)
    else:
        logger.warning("No processes found using /dev/gpiochip0 or lsof command failed")
except Exception as e:
    logger.error(f"Error checking processes using GPIO: {e}")

logger.info("GPIO check complete") 