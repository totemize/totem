"""In-memory E-Ink transport for development and CI."""

from devices.eink.eink import EInkDeviceInterface


class Driver(EInkDeviceInterface):
    IS_MOCK = True
    width = 250
    height = 122
    WIDTH = width
    HEIGHT = height

    def __init__(self):
        self.initialized = False
        self.last_image = None

    def init(self):
        self.initialized = True
        return True

    def clear(self):
        self._require_initialized()
        self.last_image = None

    def display_image(self, image):
        self._require_initialized()
        self.last_image = image

    def display_bytes(self, image_bytes):
        self._require_initialized()
        if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
            raise TypeError("E-Ink byte transport requires bytes-like data")
        self.last_image = bytes(image_bytes)

    def _require_initialized(self):
        if not self.initialized:
            raise RuntimeError("Mock E-Ink driver not initialized")
