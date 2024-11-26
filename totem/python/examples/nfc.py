import pyudev

class NFC:
    def __init__(self, driver_name: Optional[str] = None):
        if driver_name:
            self.driver = self._load_driver_by_name(driver_name)
        else:
            detected_driver = self._detect_hardware_pyudev()
            if detected_driver:
                self.driver = self._load_driver_by_name(detected_driver)
            else:
                raise RuntimeError("No compatible NFC hardware detected.")

    def _detect_hardware_pyudev(self) -> Optional[str]:
        logger.info("Detecting NFC hardware using pyudev...")
        context = pyudev.Context()
        hardware_map = {
            ('04e6', '5591'): 'acs_acr122',
            ('0483', '5740'): 'pnc532',
        }
        for device in context.list_devices(subsystem='usb'):
            vendor_id = device.attributes.get('idVendor')
            product_id = device.attributes.get('idProduct')
            if vendor_id and product_id:
                vendor_id = vendor_id.decode().lower()
                product_id = product_id.decode().lower()
                driver_name = hardware_map.get((vendor_id, product_id))
                if driver_name:
                    logger.info(f"Detected NFC device: {driver_name}")
                    return driver_name
        logger.warning("No known NFC hardware detected.")
        return None
