"""FastAPI application for Totem's synchronous hardware managers."""

import asyncio
import base64
from contextlib import asynccontextmanager
import os
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import uvicorn

from service.event_manager import EventManager
from service.models import (
    DisplayImageRequest,
    DisplayTextRequest,
    NFCDataRequest,
    NetworkConfigurationRequest,
    Status,
    StorageOperationRequest,
    StorageReadResponse,
)
from utils.logger import get_logger


logger = get_logger()
ManagerFactory = Callable[[], Any]


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _default_manager_factories() -> Dict[str, ManagerFactory]:
    allow_mock = _enabled("TOTEM_ALLOW_MOCK_DRIVERS")

    def display():
        from managers.display_manager import DisplayManager

        return DisplayManager()

    def nfc():
        from managers.nfc_manager import NFCManager

        return NFCManager(allow_mock=allow_mock)

    def network():
        from managers.network_manager import NetworkManager

        return NetworkManager(allow_mock=allow_mock)

    def storage():
        from managers.storage_manager import StorageManager

        return StorageManager(storage_root=os.environ.get("TOTEM_STORAGE_ROOT"))

    return {
        "display": display,
        "nfc": nfc,
        "network": network,
        "storage": storage,
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


async def _call_hardware(operation: Callable, *args, **kwargs):
    try:
        return await run_in_threadpool(operation, *args, **kwargs)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Hardware operation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Hardware operation failed") from exc


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
        application.state.event_manager = EventManager()
        await application.state.event_manager.start()
        try:
            yield
        finally:
            await application.state.event_manager.shutdown()

    application = FastAPI(
        title="Totem Hardware Control API",
        description="API for controlling Totem hardware components",
        version="0.2.0",
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
            "version": "0.2.0",
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
        x = int(command.position.get("x", 10))
        y = int(command.position.get("y", 10))
        await _call_hardware(
            manager.display_text, command.text, command.font_size, x, y
        )
        return Status(success=True, message="Text displayed successfully")

    @application.post("/display/image", response_model=Status)
    async def display_image(request: Request, command: DisplayImageRequest):
        manager = await _get_manager(request, "display")
        await _call_hardware(manager.display_bytes, command.image_data)
        return Status(success=True, message="Image displayed successfully")

    @application.post("/nfc/read", response_model=Status)
    async def read_nfc(request: Request):
        manager = await _get_manager(request, "nfc")
        data = await _call_hardware(manager.read_card)
        return Status(success=True, message="Data read successfully: {}".format(data))

    @application.post("/nfc/write", response_model=Status)
    async def write_nfc(request: Request, command: NFCDataRequest):
        if command.data is None:
            raise HTTPException(status_code=422, detail="NFC data is required")
        try:
            data = command.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=422, detail="NFC data must be UTF-8 encoded"
            ) from exc
        manager = await _get_manager(request, "nfc")
        await _call_hardware(manager.write_card, data)
        return Status(success=True, message="Data written successfully")

    @application.post("/storage/read", response_model=StorageReadResponse)
    async def read_storage(request: Request, command: StorageOperationRequest):
        manager = await _get_manager(request, "storage")
        data = await _call_hardware(manager.read_data, command.path)
        return StorageReadResponse(
            success=True,
            message="Data read successfully",
            data_base64=base64.b64encode(data).decode("ascii"),
        )

    @application.post("/storage/write", response_model=Status)
    async def write_storage(request: Request, command: StorageOperationRequest):
        if command.data is None:
            raise HTTPException(status_code=422, detail="Storage data is required")
        manager = await _get_manager(request, "storage")
        await _call_hardware(manager.write_data, command.path, command.data)
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
        await _call_hardware(operation, command.ssid, command.password)
        return Status(success=True, message="Network configured successfully")

    return application


app = create_app()


def start_server(host="0.0.0.0", port=8000, reload=False):
    logger.info(f"Starting Totem API server on {host}:{port}")
    uvicorn.run("service.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
