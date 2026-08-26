"""Canonical loopback-bus implementation of the screen hardware ports."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, Mapping, Optional
from urllib import error, request
from uuid import uuid4

from PIL import Image

from totem.hardware.hosts.protocol import MAX_ATTACHMENT_BYTES, ProtocolError, encode_frame
from totem.screen.ports import HardwareHealth, HardwareHealthSnapshot, PowerSnapshot, PowerStatus


class ScreenBusError(RuntimeError):
    """A stable canonical-bus error safe for screen retry and presentation."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _HardwareHealthPort(HardwareHealth):
    def __init__(self, adapter: "HardwareBusScreenAdapter") -> None:
        self._adapter = adapter

    async def snapshot(self) -> HardwareHealthSnapshot:
        result = await self._adapter._call("hardware.status.get")
        status = result.get("status")
        if not isinstance(status, Mapping):
            raise ScreenBusError("invalid_response")
        ready = status.get("ready")
        degraded = status.get("degraded")
        if not isinstance(ready, bool) or not isinstance(degraded, bool):
            raise ScreenBusError("invalid_response")
        return HardwareHealthSnapshot(ready=ready, degraded=degraded)


class _PowerStatusPort(PowerStatus):
    def __init__(self, adapter: "HardwareBusScreenAdapter") -> None:
        self._adapter = adapter

    async def snapshot(self) -> PowerSnapshot:
        result = await self._adapter._call(
            "power.telemetry.read", binding_id=self._adapter.power_binding_id
        )
        telemetry = result.get("telemetry")
        if not isinstance(telemetry, Mapping):
            raise ScreenBusError("invalid_response")
        battery_percent = telemetry.get("battery_percent")
        power_plugged = telemetry.get("power_plugged")
        if isinstance(battery_percent, bool) or not isinstance(battery_percent, (int, float)):
            raise ScreenBusError("invalid_response")
        if not 0.0 <= float(battery_percent) <= 100.0:
            raise ScreenBusError("invalid_response")
        if power_plugged is not None and not isinstance(power_plugged, bool):
            raise ScreenBusError("invalid_response")
        return PowerSnapshot(float(battery_percent), power_plugged)


class HardwareBusScreenAdapter:
    """Use only correlated canonical bus traffic for screen hardware needs."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        display_binding_id: str = "display",
        power_binding_id: str = "power",
        request_id_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.display_binding_id = display_binding_id
        self.power_binding_id = power_binding_id
        self._request_id_factory = request_id_factory or (lambda: uuid4().hex)
        self._opener = request.build_opener(request.ProxyHandler({}))
        self.health: HardwareHealth = _HardwareHealthPort(self)
        self.power: PowerStatus = _PowerStatusPort(self)

    async def wait_ready(self, timeout: float = 60.0) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            try:
                if (await self.health.snapshot()).ready:
                    return
            except ScreenBusError:
                pass
            if loop.time() >= deadline:
                raise TimeoutError("Timed out waiting for the Totem hardware bus")
            await asyncio.sleep(0.25)

    async def show(self, image: Image.Image) -> None:
        if not isinstance(image, Image.Image) or image.width <= 0 or image.height <= 0:
            raise ValueError("screen frame must be a non-empty Pillow image")
        monochrome = image if image.mode == "1" else image.convert("1")
        frame = monochrome.tobytes()
        if len(frame) > MAX_ATTACHMENT_BYTES:
            raise ValueError("screen frame exceeds the canonical attachment bound")
        request_id = self._new_request_id()
        attachment_id = "frame-{}".format(request_id)
        await self._call(
            "display.frame.write",
            request_id=request_id,
            binding_id=self.display_binding_id,
            fields={
                "frame": {
                    "attachment_id": attachment_id,
                    "width": monochrome.width,
                    "height": monochrome.height,
                    "pixel_format": "mono1",
                }
            },
            attachments={attachment_id: ("application/octet-stream", frame)},
            timeout=45.0,
        )

    async def _call(
        self,
        message_type: str,
        *,
        request_id: Optional[str] = None,
        binding_id: Optional[str] = None,
        fields: Optional[Mapping[str, object]] = None,
        attachments: Optional[Mapping[str, object]] = None,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        request_id = request_id or self._new_request_id()
        message: Dict[str, object] = {"type": message_type, "id": request_id}
        if binding_id is not None:
            message["binding_id"] = binding_id
        if fields is not None:
            message.update(fields)
        try:
            body = encode_frame(message if attachments is None else {**message, "_attachments": attachments})
        except ProtocolError as exc:
            raise ScreenBusError(exc.code) from exc
        try:
            result = await asyncio.to_thread(self._post, body, timeout)
        except (error.URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise ScreenBusError("bus_unavailable") from exc
        expected_type = "{}.result".format(message_type)
        if not isinstance(result, Mapping) or result.get("type") != expected_type or result.get("id") != request_id:
            raise ScreenBusError("invalid_response")
        if result.get("ok") is not True:
            error_value = result.get("error")
            code = error_value.get("code") if isinstance(error_value, Mapping) else None
            raise ScreenBusError(code if isinstance(code, str) else "request_failed")
        return dict(result)

    def _post(self, body: bytes, timeout: float) -> Dict[str, Any]:
        operation = request.Request(
            self.base_url + "/bus",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/octet-stream",
            },
            method="POST",
        )
        with self._opener.open(operation, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("canonical bus result is not an object")
        return value

    def _new_request_id(self) -> str:
        request_id = self._request_id_factory()
        if not isinstance(request_id, str) or not request_id:
            raise ScreenBusError("invalid_request_id")
        return request_id
