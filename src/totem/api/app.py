"""Deployed REST/WebSocket compatibility translators over the hardware bus."""

import base64
import binascii
from contextlib import asynccontextmanager
from ipaddress import ip_address
from typing import Any, Callable, Dict, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from totem import __version__
from totem.api.event_manager import EventManager
from totem.compat.hardware_client import LegacyHardwareClient, LegacyHardwareError
from totem.hardware.api.bus import HardwareBus
from totem.hardware.api.events import HardwareEventProjection
from totem.hardware.hosts.protocol import MAX_ATTACHMENT_BYTES, ProtocolError, decode_frame
from totem.api.models import (
    BLEAdvertisementRequest,
    BLEAdvertisementResponse,
    BLEDeviceOperationRequest,
    BLEDeviceResponse,
    BLEDiscoveryRequest,
    BLEDiscoveryResponse,
    BluetoothRadioResponse,
    DisplayImageRequest,
    DisplayTextRequest,
    GATTServiceResponse,
    GATTSubscriptionRequest,
    GATTSubscriptionResponse,
    GATTValueResponse,
    GATTWriteRequest,
    L2CAPConnectionRequest,
    L2CAPConnectionResponse,
    L2CAPHandoffRequest,
    L2CAPListenerRequest,
    L2CAPListenerResponse,
    NFCWriteRequest,
    NanDataPathRequest,
    NanDataPathResponse,
    NanDiscoveryRequest,
    NanDiscoverySessionResponse,
    NanFollowupRequest,
    NanFollowupResponse,
    NanMatchResponse,
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
from totem.devices.network.models import serialize
from totem.logging import get_logger


logger = get_logger()
LEGACY_ROUTE_ACTIONS: Dict[tuple[str, str], str] = {}
def _decode_base64(value: str, field_name: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="{} must be valid base64".format(field_name)
        ) from exc
    if len(decoded) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=422, detail="{} exceeds the hardware attachment bound".format(field_name)
        )
    return decoded


async def _get_manager(request: Request, _name: str) -> LegacyHardwareClient:
    """Compatibility seam: routes now receive the sole outward bus adapter."""

    return request.app.state.hardware_client


async def _call_hardware(
    request: Request, manager_name: str, operation: Callable, *args, **kwargs
):
    """Translate canonical result errors to the stable legacy HTTP boundary."""

    try:
        return operation(*args, **kwargs)
    except LegacyHardwareError as exc:
        status = {
            "invalid_request": 422,
            "unknown_type": 501,
            "host_unavailable": 503,
            "binding_unavailable": 503,
            "radio_operation_timeout": 504,
            "unsupported_feature": 501,
        }.get(exc.code, 502)
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": "hardware operation failed"},
        ) from exc


def create_app(
    *,
    client: Optional[LegacyHardwareClient] = None,
    runtime: Optional[object] = None,
    legacy_config: Optional[object] = None,
    runtime_config: Optional[object] = None,
) -> FastAPI:
    """Preserve deployed routes as translators over one injected runtime/bus."""

    bus = HardwareBus(runtime) if runtime is not None else None
    hardware_client = client or LegacyHardwareClient(
        bus
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.hardware_client = hardware_client
        application.state.legacy_runtime_config = legacy_config
        application.state.runtime_config = runtime_config
        if runtime is not None:
            runtime.start()
        application.state.event_manager = EventManager(getattr(runtime, "events", None))
        await application.state.event_manager.start()
        try:
            yield
        finally:
            await application.state.event_manager.shutdown()
            if runtime is not None:
                runtime.close()

    application = FastAPI(
        title="Totem Hardware Control API",
        description="API for controlling Totem hardware components",
        version=__version__,
        lifespan=lifespan,
    )
    # ASGI unit clients may exercise a translator without entering lifespan;
    # this is still the same injected adapter, never a fallback runtime owner.
    application.state.hardware_client = hardware_client
    application.state.legacy_runtime_config = legacy_config
    application.state.runtime_config = runtime_config
    application.state.hardware_runtime = runtime
    application.state.hardware_bus = bus
    application.state.hardware_events = (
        HardwareEventProjection(runtime.events) if runtime is not None else None
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
            "initialized_managers": [],
        }

    def loopback_or_forbidden(request: Request) -> Optional[JSONResponse]:
        client_address = request.client
        try:
            is_loopback = client_address is not None and ip_address(client_address.host).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            return JSONResponse(status_code=403, content={"detail": "loopback access required"})
        return None

    @application.post("/bus")
    async def canonical_dispatch(request: Request) -> JSONResponse:
        forbidden = loopback_or_forbidden(request)
        if forbidden is not None:
            return forbidden
        if bus is None:
            return JSONResponse(status_code=503, content={"detail": "hardware runtime unavailable"})
        try:
            message = decode_frame(await request.body())
        except ProtocolError:
            return JSONResponse(status_code=400, content={"type": "bus.error.result", "id": None, "ok": False, "error": {"code": "invalid_frame"}})
        result = bus.dispatch(message)
        return JSONResponse(status_code=202, content={"ok": True}) if result is None else JSONResponse(content=result)

    @application.get("/bus/events")
    async def canonical_events(request: Request):
        forbidden = loopback_or_forbidden(request)
        if forbidden is not None:
            return forbidden
        projection = application.state.hardware_events
        if projection is None:
            return JSONResponse(status_code=503, content={"detail": "hardware runtime unavailable"})
        return StreamingResponse(
            projection.stream(), media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

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
    async def wifi_networks(
        request: Request,
        timeout_seconds: float = Query(default=20.0, gt=0, le=120),
    ):
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
    async def wifi_disconnect(
        request: Request,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
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
    async def wifi_hotspot_stop(
        request: Request,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
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
    async def p2p_discovery_stop(
        request: Request,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
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
        request: Request,
        group_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
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
        "/network/wifi/aware/discovery",
        response_model=NanDiscoverySessionResponse,
    )
    async def nan_discovery_start(request: Request, command: NanDiscoveryRequest):
        manager = await _get_manager(request, "network")
        service_info = _decode_base64(
            command.service_info_base64, "service_info_base64"
        )
        value = await _call_hardware(
            request,
            "network",
            manager.start_nan_discovery,
            command.service_name,
            service_info,
            command.duration_seconds,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/wifi/aware/discovery",
        response_model=list[NanDiscoverySessionResponse],
    )
    async def nan_discovery_sessions(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.list_nan_discovery_sessions
        )
        return serialize(values)

    @application.delete(
        "/network/wifi/aware/discovery/{session_id}", response_model=Status
    )
    async def nan_discovery_stop(
        request: Request,
        session_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.stop_nan_discovery,
            session_id,
            timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi Aware discovery stopped")

    @application.get(
        "/network/wifi/aware/matches", response_model=list[NanMatchResponse]
    )
    async def nan_matches(request: Request, session_id: Optional[str] = None):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.list_nan_matches, session_id
        )
        return serialize(values)

    @application.post(
        "/network/wifi/aware/followups", response_model=NanFollowupResponse
    )
    async def nan_followup_send(request: Request, command: NanFollowupRequest):
        manager = await _get_manager(request, "network")
        payload = _decode_base64(command.payload_base64, "payload_base64")
        value = await _call_hardware(
            request,
            "network",
            manager.send_nan_followup,
            command.match_id,
            payload,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/wifi/aware/followups", response_model=list[NanFollowupResponse]
    )
    async def nan_followups(request: Request, session_id: Optional[str] = None):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.list_nan_followups, session_id
        )
        return serialize(values)

    @application.post(
        "/network/wifi/aware/data-paths", response_model=NanDataPathResponse
    )
    async def nan_data_path_create(request: Request, command: NanDataPathRequest):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.create_nan_data_path,
            command.match_id,
            command.port,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/wifi/aware/data-paths", response_model=list[NanDataPathResponse]
    )
    async def nan_data_paths(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(request, "network", manager.list_nan_data_paths)
        return serialize(values)

    @application.delete(
        "/network/wifi/aware/data-paths/{data_path_id}", response_model=Status
    )
    async def nan_data_path_remove(
        request: Request,
        data_path_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.remove_nan_data_path,
            data_path_id,
            timeout_seconds,
        )
        return Status(success=True, message="Wi-Fi Aware data path removed")

    @application.post(
        "/network/bluetooth/discovery", response_model=BLEDiscoveryResponse
    )
    async def bluetooth_discovery_start(request: Request, command: BLEDiscoveryRequest):
        manager = await _get_manager(request, "network")
        # The NIP-5D discovery capability owns its fixed discovery policy;
        # legacy duration/filter knobs were removed with the old radio API.
        session_id = await _call_hardware(request, "network", manager.start_bluetooth_discovery)
        return BLEDiscoveryResponse(session_id=session_id)

    @application.delete("/network/bluetooth/discovery", response_model=Status)
    async def bluetooth_discovery_stop(
        request: Request,
        session_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
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
        request: Request,
        advertisement_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
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
        "/network/bluetooth/l2cap/listeners",
        response_model=L2CAPListenerResponse,
    )
    async def l2cap_listener_create(request: Request, command: L2CAPListenerRequest):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.create_l2cap_listener,
            command.service_uuid,
            command.psm,
            command.mtu,
            command.address_type,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/bluetooth/l2cap/listeners",
        response_model=list[L2CAPListenerResponse],
    )
    async def l2cap_listeners(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(request, "network", manager.list_l2cap_listeners)
        return serialize(values)

    @application.delete(
        "/network/bluetooth/l2cap/listeners/{listener_id}", response_model=Status
    )
    async def l2cap_listener_close(
        request: Request,
        listener_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.close_l2cap_listener,
            listener_id,
            timeout_seconds,
        )
        return Status(success=True, message="LE L2CAP listener closed")

    @application.post(
        "/network/bluetooth/l2cap/connections",
        response_model=L2CAPConnectionResponse,
    )
    async def l2cap_connection_create(
        request: Request, command: L2CAPConnectionRequest
    ):
        manager = await _get_manager(request, "network")
        value = await _call_hardware(
            request,
            "network",
            manager.connect_l2cap,
            command.peer_address,
            command.psm,
            command.mtu,
            command.address_type,
            command.timeout_seconds,
        )
        return serialize(value)

    @application.get(
        "/network/bluetooth/l2cap/connections",
        response_model=list[L2CAPConnectionResponse],
    )
    async def l2cap_connections(request: Request):
        manager = await _get_manager(request, "network")
        values = await _call_hardware(
            request, "network", manager.list_l2cap_connections
        )
        return serialize(values)

    @application.delete(
        "/network/bluetooth/l2cap/connections/{connection_id}",
        response_model=Status,
    )
    async def l2cap_connection_close(request: Request, connection_id: str):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request, "network", manager.close_l2cap_connection, connection_id
        )
        return Status(success=True, message="LE L2CAP connection closed")

    @application.post(
        "/network/bluetooth/l2cap/connections/{connection_id}/fips-handoff",
        response_model=Status,
    )
    async def l2cap_connection_handoff(
        request: Request, connection_id: str, command: L2CAPHandoffRequest
    ):
        manager = await _get_manager(request, "network")
        await _call_hardware(
            request,
            "network",
            manager.handoff_l2cap_to_fips,
            connection_id,
            command.timeout_seconds,
        )
        return Status(success=True, message="LE L2CAP connection handed to FIPS")

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
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
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
        request: Request,
        subscription_id: str,
        timeout_seconds: float = Query(default=15.0, gt=0, le=120),
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
        status = await _call_hardware(request, "ups", manager.get_ups_status)
        if isinstance(status, dict):
            return UPSStatusResponse(**status)
        return UPSStatusResponse(
            model=status.model,
            battery_percent=status.battery_percent,
            voltage_volts=status.voltage_volts,
            current_amps=status.current_amps,
            power_plugged=status.power_plugged,
        )

    LEGACY_ROUTE_ACTIONS.clear()
    for route in application.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or path in {"/", "/health", "/bus", "/bus/events", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}:
            continue
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None:
            LEGACY_ROUTE_ACTIONS[(next(iter(methods)), path)] = "legacy.{}".format(endpoint.__name__)

    return application


app = create_app()


def start_server(host="0.0.0.0", port=8000, reload=False):
    """Keep the ``totem-api`` entry point on the same composed application."""

    from totem.__main__ import compose_application

    logger.info(f"Starting Totem API server on {host}:{port}")
    uvicorn.run(compose_application(), host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
