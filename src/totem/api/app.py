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
    BLEAdvertisementRequest,
    BLEAdvertisementResponse,
    BLEDeviceOperationRequest,
    BLEDeviceResponse,
    BLEDiscoveryRequest,
    BLEDiscoveryResponse,
    BluetoothRadioResponse,
    DeviceEvent,
    DeviceId,
    DeviceType,
    DisplayImageRequest,
    DisplayTextRequest,
    EventType,
    GATTServiceResponse,
    GATTSubscriptionRequest,
    GATTSubscriptionResponse,
    GATTValueResponse,
    GATTWriteRequest,
    NFCWriteRequest,
    NetworkCapabilitiesResponse,
    NetworkConfigurationRequest,
    NetworkStatusResponse,
    P2PDiscoveryRequest,
    P2PGroupRequest,
    P2PGroupResponse,
    P2PPeerResponse,
    RadioRequest,
    Status,
    StorageReadRequest,
    StorageReadResponse,
    StorageWriteRequest,
    UPSStatusResponse,
    WiFiConnectionRequest,
    WiFiNetworkResponse,
    WiFiRadioResponse,
)
from totem.devices.network.errors import RadioOperationError
from totem.devices.network.models import serialize
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
            if name == "network":
                setter = getattr(manager, "set_event_callback", None)
                if setter is not None:
                    setter(request.app.state.radio_event_callback)
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
        except RadioOperationError as exc:
            logger.warning("%s radio operation rejected: %s", manager_name, exc.code)
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": exc.detail},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_radio_request", "message": str(exc)},
            ) from exc
        except Exception as exc:
            logger.error("%s hardware operation failed: %s", manager_name, exc)
            raise HTTPException(
                status_code=502,
                detail="{} hardware operation failed".format(manager_name.capitalize()),
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
        application.state.manager_locks = {name: asyncio.Lock() for name in factories}
        application.state.operation_locks = {name: asyncio.Lock() for name in factories}
        application.state.event_manager = EventManager()
        await application.state.event_manager.start()
        application.state.loop = asyncio.get_running_loop()

        def radio_event_callback(event_name: str, data: Dict[str, Any]) -> None:
            try:
                event_type = EventType(event_name)
            except ValueError:
                event_type = EventType.HARDWARE_EVENT
            event = DeviceEvent(
                device=DeviceId(device_type=DeviceType.NETWORK),
                event_type=event_type,
                data=data,
            )
            asyncio.run_coroutine_threadsafe(
                application.state.event_manager.publish_event(event),
                application.state.loop,
            )

        application.state.radio_event_callback = radio_event_callback
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
        data = await _call_hardware(request, "storage", manager.read_data, command.path)
        return StorageReadResponse(
            success=True,
            message="Data read successfully",
            data_base64=base64.b64encode(data).decode("ascii"),
        )

    @application.post("/storage/write", response_model=Status)
    async def write_storage(request: Request, command: StorageWriteRequest):
        manager = await _get_manager(request, "storage")
        data = _decode_base64(command.data_base64, "data_base64")
        await _call_hardware(request, "storage", manager.write_data, command.path, data)
        return Status(success=True, message="Data written successfully")

    @application.post("/network/configure", response_model=Status)
    async def configure_network(request: Request, command: NetworkConfigurationRequest):
        manager = await _get_manager(request, "network")
        operation = (
            manager.create_hotspot if command.is_hotspot else manager.connect_to_network
        )
        await _call_hardware(
            request, "network", operation, command.ssid, command.password
        )
        return Status(success=True, message="Network configured successfully")

    @application.get(
        "/network/capabilities", response_model=NetworkCapabilitiesResponse
    )
    async def network_capabilities(request: Request):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(request, "network", manager.get_capabilities)
        return serialize(value)

    @application.get("/network/status", response_model=NetworkStatusResponse)
    async def network_status(request: Request):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(request, "network", manager.get_status)
        return serialize(value)

    @application.put("/network/wifi/radio", response_model=WiFiRadioResponse)
    async def wifi_radio(request: Request, command: RadioRequest):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.set_wifi_radio_enabled,
            command.enabled,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.put("/network/bluetooth/radio", response_model=BluetoothRadioResponse)
    async def bluetooth_radio(request: Request, command: RadioRequest):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.set_bluetooth_radio_enabled,
            command.enabled,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get("/network/wifi/networks", response_model=list[WiFiNetworkResponse])
    async def wifi_networks(request: Request, timeout_seconds: float = 20.0):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.scan_wifi_networks, timeout_seconds
        )
        return serialize(values)

    @application.post("/network/wifi/connections", response_model=Status)
    async def wifi_connect(request: Request, command: WiFiConnectionRequest):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.connect_to_network,
            command.ssid,
            command.password,
            command.timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi station connection activated")

    @application.delete("/network/wifi/connections", response_model=Status)
    async def wifi_disconnect(request: Request, timeout_seconds: float = 15.0):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request, "network", manager.disconnect_from_network, timeout_seconds
        )
        return Status(success=True, message="Wi-Fi station connection deactivated")

    @application.post("/network/wifi/hotspots", response_model=Status)
    async def wifi_hotspot(request: Request, command: WiFiConnectionRequest):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.create_hotspot,
            command.ssid,
            command.password,
            command.timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi hotspot activated")

    @application.delete("/network/wifi/hotspots", response_model=Status)
    async def wifi_hotspot_stop(request: Request, timeout_seconds: float = 15.0):
        manager = await _get_manager(request, "network")
        await _call_hardware(request, "network", manager.stop_hotspot, timeout_seconds)
        return Status(success=True, message="Wi-Fi hotspot deactivated")

    @application.post("/network/wifi/p2p/discovery", response_model=Status)
    async def p2p_discovery_start(request: Request, command: P2PDiscoveryRequest):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.start_p2p_discovery,
            command.duration_seconds,
            command.timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi Direct discovery started")

    @application.delete("/network/wifi/p2p/discovery", response_model=Status)
    async def p2p_discovery_stop(request: Request, timeout_seconds: float = 15.0):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request, "network", manager.stop_p2p_discovery, timeout_seconds
        )
        return Status(success=True, message="Wi-Fi Direct discovery stopped")

    @application.get("/network/wifi/p2p/peers", response_model=list[P2PPeerResponse])
    async def p2p_peers(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(request, "network", manager.list_p2p_peers)
        return serialize(values)

    @application.post("/network/wifi/p2p/groups", response_model=P2PGroupResponse)
    async def p2p_group_create(request: Request, command: P2PGroupRequest):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.create_p2p_group,
            command.peer_id,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get("/network/wifi/p2p/groups", response_model=list[P2PGroupResponse])
    async def p2p_groups(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(request, "network", manager.list_p2p_groups)
        return serialize(values)

    @application.delete("/network/wifi/p2p/groups/{group_id}", response_model=Status)
    async def p2p_group_remove(
        request: Request, group_id: str, timeout_seconds: float = 15.0
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.remove_p2p_group,
            group_id,
            timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi Direct group removed")

    @application.post(
        "/network/bluetooth/discovery", response_model=BLEDiscoveryResponse
    )
    async def bluetooth_discovery_start(request: Request, command: BLEDiscoveryRequest):
        manager = await _get_manager(request, "network")
        session_id = await _call_hardware(
            request,
            "network",
            manager.start_bluetooth_discovery,
            duration_seconds=command.duration_seconds,
            service_uuids=command.service_uuids,
            duplicate_data=command.duplicate_data,
            session_id=command.session_id,
            timeout=command.timeout_seconds,
        )
        return BLEDiscoveryResponse(session_id=session_id)

    @application.delete("/network/bluetooth/discovery", response_model=Status)
    async def bluetooth_discovery_stop(
        request: Request, session_id: str, timeout_seconds: float = 15.0
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.stop_bluetooth_discovery,
            session_id,
            timeout_seconds,
        )
        return Status(success=True, message="BLE discovery session stopped")

    @application.get(
        "/network/bluetooth/devices", response_model=list[BLEDeviceResponse]
    )
    async def bluetooth_devices(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.list_bluetooth_devices
        )
        return serialize(values)

    @application.post(
        "/network/bluetooth/advertisements",
        response_model=BLEAdvertisementResponse,
    )
    async def bluetooth_advertisement_register(
        request: Request, command: BLEAdvertisementRequest
    ):
        manager = await _get_manager(request, "network")
        specification = {
            "id": command.id,
            "type": command.type,
            "service_uuids": command.service_uuids,
            "service_data": {
                key: _decode_base64(value, "service_data_base64")
                for key, value in command.service_data_base64.items()
            },
            "manufacturer_data": {
                key: _decode_base64(value, "manufacturer_data_base64")
                for key, value in command.manufacturer_data_base64.items()
            },
            "local_name": command.local_name,
            "includes": command.includes,
        }
        value = await _call_hardware(
            request,
            "network",
            manager.register_bluetooth_advertisement,
            specification,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.delete(
        "/network/bluetooth/advertisements/{advertisement_id}",
        response_model=Status,
    )
    async def bluetooth_advertisement_unregister(
        request: Request, advertisement_id: str, timeout_seconds: float = 15.0
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.unregister_bluetooth_advertisement,
            advertisement_id,
            timeout_seconds,
        )
        return Status(success=True, message="BLE advertisement unregistered")

    @application.post(
        "/network/bluetooth/devices/{device_id}/connect",
        response_model=BLEDeviceResponse,
    )
    async def bluetooth_device_connect(
        request: Request, device_id: str, command: BLEDeviceOperationRequest
    ):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.connect_bluetooth_device,
            device_id,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.post(
        "/network/bluetooth/devices/{device_id}/disconnect",
        response_model=BLEDeviceResponse,
    )
    async def bluetooth_device_disconnect(
        request: Request, device_id: str, command: BLEDeviceOperationRequest
    ):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.disconnect_bluetooth_device,
            device_id,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/bluetooth/devices/{device_id}/gatt",
        response_model=list[GATTServiceResponse],
    )
    async def bluetooth_gatt(request: Request, device_id: str):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(request, "network", manager.list_gatt, device_id)
        return serialize(values)

    @application.get(
        "/network/bluetooth/devices/{device_id}/gatt/characteristics/{characteristic_id}",
        response_model=GATTValueResponse,
    )
    async def bluetooth_gatt_read(
        request: Request,
        device_id: str,
        characteristic_id: str,
        timeout_seconds: float = 15.0,
    ):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.read_gatt_characteristic,
            device_id,
            characteristic_id,
            timeout_seconds,
        )
        return GATTValueResponse(value_base64=base64.b64encode(value).decode("ascii"))

    @application.put(
        "/network/bluetooth/devices/{device_id}/gatt/characteristics/{characteristic_id}",
        response_model=Status,
    )
    async def bluetooth_gatt_write(
        request: Request,
        device_id: str,
        characteristic_id: str,
        command: GATTWriteRequest,
    ):
        manager = await _get_manager(request, "network")
        value = _decode_base64(command.value_base64, "value_base64")
        await _call_hardware(
            request,
            "network",
            manager.write_gatt_characteristic,
            device_id,
            characteristic_id,
            value,
            command.with_response,
            command.timeout_seconds,
        )
        return Status(success=True, message="GATT characteristic written")

    @application.post(
        "/network/bluetooth/devices/{device_id}/gatt/characteristics/"
        "{characteristic_id}/subscriptions",
        response_model=GATTSubscriptionResponse,
    )
    async def bluetooth_gatt_subscribe(
        request: Request,
        device_id: str,
        characteristic_id: str,
        command: GATTSubscriptionRequest,
    ):
        manager = await _get_manager(request, "network")
        subscription_id = await _call_hardware(
            request,
            "network",
            manager.subscribe_gatt_characteristic,
            device_id,
            characteristic_id,
            command.subscription_id,
            command.timeout_seconds,
        )
        return GATTSubscriptionResponse(subscription_id=subscription_id)

    @application.delete(
        "/network/bluetooth/gatt/subscriptions/{subscription_id}",
        response_model=Status,
    )
    async def bluetooth_gatt_unsubscribe(
        request: Request, subscription_id: str, timeout_seconds: float = 15.0
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.unsubscribe_gatt_characteristic,
            subscription_id,
            timeout_seconds,
        )
        return Status(success=True, message="GATT subscription removed")

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
