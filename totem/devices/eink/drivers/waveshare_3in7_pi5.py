import time
import logging
import traceback

logger = logging.getLogger(__name__)

class Waveshare3in7Pi5:
    # ... existing code ...

    def wait_until_idle(self):
        if self.USE_HARDWARE:
            try:
                logger.debug("Waiting for display to be idle")
                # Properly handle busy_values which is a list, not a dictionary
                busy_values = self.busy_request.get_values()
                # Check if we have any values returned
                if busy_values:
                    # For gpiod 2.x, busy_values might be a list with a single value
                    busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(self.busy_pin)
                    while busy_value == self.Value.ACTIVE:
                        time.sleep(0.1)
                        busy_values = self.busy_request.get_values()
                        busy_value = busy_values[0] if isinstance(busy_values, list) else busy_values.get(self.busy_pin)
                else:
                    # If we can't read the busy pin, just wait a fixed time
                    logger.warning("Could not read busy pin, waiting fixed time instead")
                    time.sleep(1.0)
            except Exception as e:
                logger.error(f"Error waiting for idle: {e}")
                logger.error(traceback.format_exc())
                # Still wait a bit in case of error
                time.sleep(1.0)
        else:
            logger.debug("Mock wait until idle")
            time.sleep(0.5)

    def send_data(self, data):
        if self.USE_HARDWARE:
            try:
                self.dc_request.set_values({self.dc_pin: self.Value.ACTIVE})  # Data mode
                # CS is handled automatically by the SPI driver
                
                if isinstance(data, int):
                    self.spi.writebytes([data])
                else:
                    # Send data in chunks to avoid overflow
                    chunk_size = 1024  # Safe chunk size
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i + chunk_size]
                        self.spi.writebytes(chunk)
                        # Small delay between chunks to avoid overwhelming the SPI bus
                        time.sleep(0.001)
            except Exception as e:
                logger.error(f"Error sending data: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.debug(f"Mock send data: {data if isinstance(data, int) else '(data array)'}")

    # ... existing code ...