"""FastAPI application for Totem's synchronous hardware managers."""

import asyncio
import base64
import binascii
from contextlib import asynccontextmanager
import os
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import uvicorn

from totem import __version__
from totem.api.event_manager import EventManager
from totem.api.models import (
    DisplayImageRequest,
    DisplayRefreshMode,
    DisplayTextRequest,
    NFCWriteRequest,
    NetworkConfigurationRequest,
    Status,
    StorageReadRequest,
    StorageReadResponse,
    StorageWriteRequest,
    UPSStatusResponse,
)
from totem.logging import get_logger


logger = get_logger()
ManagerFactory = Callable[[], Any]


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _decode_base64(value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="{} must be valid base64".format(field_name)
        ) from exc


def _default_manager_factories() -> Dict[str, ManagerFactory]:
    allow_mock = _enabled("TOTEM_ALLOW_MOCK_DRIVERS")

    def display():
        from totem.managers.display_manager import DisplayManager

        return DisplayManager(allow_mock=allow_mock)

    def nfc():
        from totem.managers.nfc_manager import NFCManager

        return NFCManager(allow_mock=allow_mock)

    def network():
        from totem.managers.network_manager import NetworkManager

        return NetworkManager(allow_mock=allow_mock)

    def storage():
        from totem.managers.storage_manager import StorageManager

        return StorageManager(storage_root=os.environ.get("TOTEM_STORAGE_ROOT"))

    def ups():
        from totem.managers.ups_manager import UPSManager

        return UPSManager()

    return {
        "display": display,
        "nfc": nfc,
        "network": network,
        "storage": storage,
        "ups": ups,
    }


async def _get_manager(request: Request, name: str):
    manager = request.app.state.managers.get(name)
    if manager is not None:
        return manager

    async with request.app.state.manager_locks[name]:
        manager = request.app.state.managers.get(name)
        if manager is None:
            factory = request.app.state.manager_factories[name]
            try:
                manager = await run_in_threadpool(factory)
            except Exception as exc:
                logger.error("Unable to initialize %s manager: %s", name, exc)
                raise HTTPException(
                    status_code=503,
                    detail="{} hardware is unavailable".format(name.capitalize()),
                ) from exc
            request.app.state.managers[name] = manager
        return manager


async def _call_hardware(
    request: Request, manager_name: str, operation: Callable, *args, **kwargs
):
    """Serialize operations per device while keeping sync drivers off the event loop."""
    async with request.app.state.operation_locks[manager_name]:
        try:
            return await run_in_threadpool(operation, *args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("%s hardware operation failed: %s", manager_name, exc)
            raise HTTPException(
                status_code=502,
                detail="{} hardware operation failed".format(
                    manager_name.capitalize()
                ),
            ) from exc


def create_app(
    manager_factories: Optional[Dict[str, ManagerFactory]] = None,
) -> FastAPI:
    factories = _default_manager_factories()
    if manager_factories:
        factories.update(manager_factories)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.managers = {}
        application.state.manager_factories = factories
        application.state.manager_locks = {
            name: asyncio.Lock() for name in factories
        }
        application.state.operation_locks = {
            name: asyncio.Lock() for name in factories
        }
        application.state.event_manager = EventManager()
        await application.state.event_manager.start()
        try:
            yield
        finally:
            for manager in application.state.managers.values():
                close = getattr(manager, "close", None)
                if close is not None:
                    await run_in_threadpool(close)
            await application.state.event_manager.shutdown()

    application = FastAPI(
        title="Totem Hardware Control API",
        description="API for controlling Totem hardware components",
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/")
    async def root():
        return {
            "name": "Totem Hardware Control API",
            "version": __version__,
            "status": "running",
        }

    @application.get("/health")
    async def health(request: Request):
        return {
            "status": "healthy",
            "initialized_managers": sorted(request.app.state.managers),
        }

    @application.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        event_manager = websocket.app.state.event_manager
        await event_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await event_manager.disconnect(websocket)

    @application.post("/display/text", response_model=Status)
    async def display_text(request: Request, command: DisplayTextRequest):
        manager = await _get_manager(request, "display")
        await _call_hardware(
            request,
            "display",
            manager.display_text,
            command.text,
            command.font_size,
            command.x,
            command.y,
        )
        return Status(success=True, message="Text displayed successfully")

    @application.post("/display/image", response_model=Status)
    async def display_image(request: Request, command: DisplayImageRequest):
        manager = await _get_manager(request, "display")
        image_data = _decode_base64(command.image_base64, "image_base64")
        if command.refresh_mode == DisplayRefreshMode.PARTIAL:
            await _call_hardware(
                request,
                "display",
                manager.display_encoded_image,
                image_data,
                command.refresh_mode.value,
            )
        else:
            # Keep the original one-argument manager call for old clients and
            # injected manager implementations when the request omits a mode.
            await _call_hardware(
                request, "display", manager.display_encoded_image, image_data
            )
        return Status(success=True, message="Image displayed successfully")

    @application.post("/nfc/read", response_model=Status)
    async def read_nfc(request: Request):
        manager = await _get_manager(request, "nfc")
        data = await _call_hardware(request, "nfc", manager.read_card)
        return Status(success=True, message="Data read successfully: {}".format(data))

    @application.post("/nfc/write", response_model=Status)
    async def write_nfc(request: Request, command: NFCWriteRequest):
        manager = await _get_manager(request, "nfc")
        await _call_hardware(request, "nfc", manager.write_card, command.data)
        return Status(success=True, message="Data written successfully")

    @application.post("/storage/read", response_model=StorageReadResponse)
    async def read_storage(request: Request, command: StorageReadRequest):
        manager = await _get_manager(request, "storage")
        data = await _call_hardware(
            request, "storage", manager.read_data, command.path
        )
        return StorageReadResponse(
            success=True,
            message="Data read successfully",
            data_base64=base64.b64encode(data).decode("ascii"),
        )

    @application.post("/storage/write", response_model=Status)
    async def write_storage(request: Request, command: StorageWriteRequest):
        manager = await _get_manager(request, "storage")
        data = _decode_base64(command.data_base64, "data_base64")
        await _call_hardware(
            request, "storage", manager.write_data, command.path, data
        )
        return Status(success=True, message="Data written successfully")

    @application.post("/network/configure", response_model=Status)
    async def configure_network(
        request: Request, command: NetworkConfigurationRequest
    ):
        manager = await _get_manager(request, "network")
        operation = (
            manager.create_hotspot
            if command.is_hotspot
            else manager.connect_to_network
        )
        await _call_hardware(
            request, "network", operation, command.ssid, command.password
        )
        return Status(success=True, message="Network configured successfully")

    @application.get("/ups/status", response_model=UPSStatusResponse)
    async def ups_status(request: Request):
        manager = await _get_manager(request, "ups")
        status = await _call_hardware(request, "ups", manager.get_status)
        return UPSStatusResponse(
            model=status.model,
            battery_percent=status.battery_percent,
            voltage_volts=status.voltage_volts,
            current_amps=status.current_amps,
            power_plugged=status.power_plugged,
        )

    return application


app = create_app()


def start_server(host="0.0.0.0", port=8000, reload=False):
    logger.info(f"Starting Totem API server on {host}:{port}")
    uvicorn.run("totem.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
