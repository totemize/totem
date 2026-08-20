"""Client for the device-manager display boundary."""

import asyncio
import base64
import io
import json
from typing import Any, Dict, Optional
from urllib import error, request

from PIL import Image


class DeviceManagerDisplay:
    """Submit complete frames without claiming SPI/GPIO in this process."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self._opener = request.build_opener(request.ProxyHandler({}))

    def _request(
        self,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        operation = request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method="POST" if data is not None else "GET",
        )
        with self._opener.open(operation, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    async def ready(self) -> bool:
        try:
            response = await asyncio.to_thread(self._request, "/health")
        except (error.URLError, OSError, TimeoutError, ValueError):
            return False
        return response.get("status") == "healthy"

    async def wait_ready(self, timeout: float = 60.0) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not await self.ready():
            if loop.time() >= deadline:
                raise TimeoutError("Timed out waiting for the Totem device API")
            await asyncio.sleep(0.25)

    async def show(self, image: Image.Image) -> None:
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        payload = {"image_base64": base64.b64encode(encoded.getvalue()).decode("ascii")}
        response = await asyncio.to_thread(
            self._request,
            "/display/image",
            payload=payload,
            timeout=45.0,
        )
        if not response.get("success"):
            raise RuntimeError("Device API rejected display frame")
