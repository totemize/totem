"""Loopback-only canonical application over one hardware runtime owner."""

from __future__ import annotations

from contextlib import asynccontextmanager
from ipaddress import ip_address
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from totem.hardware.hosts.protocol import ProtocolError, decode_frame

from .bus import HardwareBus
from .events import HardwareEventProjection
from .health import project_health


def _is_loopback(request: Request) -> bool:
    """Trust only the ASGI peer address; forwarded headers are caller input."""

    client = request.client
    if client is None:
        return False
    try:
        return ip_address(client.host).is_loopback
    except ValueError:
        return False


def create_hardware_app(
    bus: Optional[HardwareBus] = None,
    *,
    runtime: Optional[object] = None,
    runtime_factory: Optional[Callable[[], object]] = None,
) -> FastAPI:
    """Create the canonical local bus without creating parallel hardware state.

    The runtime is either injected or constructed exactly once by the explicit
    factory.  The positional bus form is retained solely for the prior tracer
    migration seam, where the bus itself owns no runtime.
    """

    if runtime is None and bus is not None and not isinstance(bus, HardwareBus):
        runtime, bus = bus, None
    if runtime is not None and runtime_factory is not None:
        raise ValueError("provide an injected runtime or a runtime factory, not both")
    if runtime is None and runtime_factory is not None:
        runtime = runtime_factory()
    if bus is None:
        if runtime is None:
            raise ValueError("hardware app requires a runtime or a bus migration seam")
        bus = HardwareBus(runtime)
    if runtime is None:
        runtime = bus.runtime
    events = HardwareEventProjection(runtime.events) if runtime is not None else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if runtime is not None:
            runtime.start()
        try:
            yield
        finally:
            if runtime is not None:
                runtime.close()

    app = FastAPI(lifespan=lifespan)
    app.state.hardware_runtime = runtime
    app.state.hardware_events = events

    def loopback_or_forbidden(request: Request) -> Optional[JSONResponse]:
        if not _is_loopback(request):
            return JSONResponse(status_code=403, content={"detail": "loopback access required"})
        return None

    @app.post("/bus")
    async def dispatch(request: Request) -> JSONResponse:
        forbidden = loopback_or_forbidden(request)
        if forbidden is not None:
            return forbidden
        try:
            message = decode_frame(await request.body())
        except ProtocolError:
            return JSONResponse(
                status_code=400,
                content={"type": "bus.error.result", "id": None, "ok": False, "error": {"code": "invalid_frame"}},
            )
        result = bus.dispatch(message)
        if result is None:
            return JSONResponse(status_code=202, content={"ok": True})
        return JSONResponse(content=result)

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        forbidden = loopback_or_forbidden(request)
        if forbidden is not None:
            return forbidden
        if runtime is None:
            return JSONResponse(status_code=503, content={"ready": False, "state": "unavailable"})
        return JSONResponse(content=project_health(runtime.health()))

    @app.get("/bus/events")
    async def bus_events(request: Request):
        forbidden = loopback_or_forbidden(request)
        if forbidden is not None:
            return forbidden
        if events is None:
            return JSONResponse(status_code=503, content={"detail": "hardware runtime unavailable"})
        return StreamingResponse(
            events.stream(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    return app
