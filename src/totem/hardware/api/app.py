"""Minimal loopback ASGI application for the canonical hardware bus tracer."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from totem.hardware.hosts.protocol import ProtocolError, decode_frame

from .bus import HardwareBus


def create_hardware_app(bus: HardwareBus) -> FastAPI:
    """Create the local POST /bus tracer over the shared framed envelope."""

    app = FastAPI()

    @app.post("/bus")
    async def dispatch(request: Request) -> JSONResponse:
        try:
            message = decode_frame(await request.body())
        except ProtocolError:
            return JSONResponse(
                status_code=400,
                content={"type": "bus.error.result", "id": None, "ok": False, "error": {"code": "invalid_frame"}},
            )
        return JSONResponse(content=bus.dispatch(message))

    return app
