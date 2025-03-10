"""
FastAPI application for Totem hardware control.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio

from utils.logger import get_logger
from service.event_manager import EventManager
from service.models import DeviceType, DeviceId, Status, DeviceState
from service.models import DisplayTextRequest, DisplayImageRequest, NFCDataRequest
from service.models import StorageOperationRequest, NetworkConfigurationRequest

# Create FastAPI app
app = FastAPI(
    title="Totem Hardware Control API",
    description="API for controlling Totem hardware components",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Get logger
logger = get_logger()

# Get event manager
event_manager = EventManager.get_instance()

# Device managers will be initialized when they're needed
display_manager = None
nfc_manager = None
network_manager = None
storage_manager = None

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "name": "Totem Hardware Control API",
        "version": "0.1.0",
        "status": "running"
    }

# WebSocket endpoint for real-time events
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time device events."""
    await websocket.accept()
    await event_manager.connect(websocket)
    
    try:
        # Keep the connection open
        while True:
            # Wait for any message from the client
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Handle disconnect
        await event_manager.disconnect(websocket)

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

# Display endpoints
@app.post("/display/text", response_model=Status)
async def display_text(request: DisplayTextRequest):
    """Display text on the e-ink screen."""
    global display_manager
    
    if display_manager is None:
        # Lazy load the display manager
        from managers.display_manager import DisplayManager
        display_manager = DisplayManager()
        await display_manager.initialize()
    
    success = await display_manager.display_text(request.device_id, request.text, 
                                              request.font_size, request.position)
    
    return Status(
        success=success,
        message="Text displayed successfully" if success else "Failed to display text"
    )

@app.post("/display/image", response_model=Status)
async def display_image(request: DisplayImageRequest):
    """Display an image on the e-ink screen."""
    global display_manager
    
    if display_manager is None:
        # Lazy load the display manager
        from managers.display_manager import DisplayManager
        display_manager = DisplayManager()
        await display_manager.initialize()
    
    success = await display_manager.display_image(request.device_id, request.image_data, 
                                              request.format, request.position)
    
    return Status(
        success=success,
        message="Image displayed successfully" if success else "Failed to display image"
    )

# NFC endpoints
@app.post("/nfc/read", response_model=Status)
async def read_nfc():
    """Read data from an NFC tag."""
    global nfc_manager
    
    if nfc_manager is None:
        # Lazy load the NFC manager
        from managers.nfc_manager import NFCManager
        nfc_manager = NFCManager()
        await nfc_manager.initialize()
    
    data = await nfc_manager.read_tag()
    
    return Status(
        success=data is not None,
        message=f"Data read successfully: {data}" if data else "Failed to read NFC tag"
    )

@app.post("/nfc/write", response_model=Status)
async def write_nfc(request: NFCDataRequest):
    """Write data to an NFC tag."""
    global nfc_manager
    
    if nfc_manager is None:
        # Lazy load the NFC manager
        from managers.nfc_manager import NFCManager
        nfc_manager = NFCManager()
        await nfc_manager.initialize()
    
    success = await nfc_manager.write_tag(request.data, request.format)
    
    return Status(
        success=success,
        message="Data written successfully" if success else "Failed to write to NFC tag"
    )

# Storage endpoints
@app.post("/storage/read", response_model=Status)
async def read_storage(request: StorageOperationRequest):
    """Read data from storage."""
    global storage_manager
    
    if storage_manager is None:
        # Lazy load the storage manager
        from managers.storage_manager import StorageManager
        storage_manager = StorageManager()
        await storage_manager.initialize()
    
    data = await storage_manager.read_file(request.device_id, request.path)
    
    return Status(
        success=data is not None,
        message=f"Data read successfully" if data else "Failed to read from storage"
    )

@app.post("/storage/write", response_model=Status)
async def write_storage(request: StorageOperationRequest):
    """Write data to storage."""
    global storage_manager
    
    if storage_manager is None:
        # Lazy load the storage manager
        from managers.storage_manager import StorageManager
        storage_manager = StorageManager()
        await storage_manager.initialize()
    
    success = await storage_manager.write_file(request.device_id, request.path, request.data)
    
    return Status(
        success=success,
        message="Data written successfully" if success else "Failed to write to storage"
    )

# Network endpoints
@app.post("/network/configure", response_model=Status)
async def configure_network(request: NetworkConfigurationRequest):
    """Configure network settings."""
    global network_manager
    
    if network_manager is None:
        # Lazy load the network manager
        from managers.network_manager import NetworkManager
        network_manager = NetworkManager()
        await network_manager.initialize()
    
    success = await network_manager.configure_wifi(
        request.device_id, request.ssid, request.password, request.is_hotspot
    )
    
    return Status(
        success=success,
        message="Network configured successfully" if success else "Failed to configure network"
    )

# Function to start the server programmatically
def start_server(host="0.0.0.0", port=8000, reload=False):
    """Start the FastAPI server."""
    logger.info(f"Starting Totem API server on {host}:{port}")
    uvicorn.run(
        "service.main:app",
        host=host,
        port=port,
        reload=reload
    )

# For direct execution
if __name__ == "__main__":
    start_server() 