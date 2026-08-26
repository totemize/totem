import asyncio
import logging
from queue import Empty
from typing import Awaitable, Callable, Dict, List, Optional, Set
from fastapi import WebSocket

from totem.api.models import DeviceEvent, DeviceType, EventType

logger = logging.getLogger(__name__)


class EventManager:
    """
    EventManager handles broadcasting device events to WebSocket clients and event subscribers.
    It also provides methods for device managers to publish events.
    """
    def __init__(self, runtime_events=None):
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Event subscribers (callbacks) by device type and event type
        self.event_subscribers: Dict[DeviceType, Dict[EventType, List[Callable[[DeviceEvent], Awaitable[None]]]]] = {
            device_type: {event_type: [] for event_type in EventType} 
            for device_type in DeviceType
        }
        
        # Compatibility-only queue for callers that do not provide the canonical
        # runtime stream.  The app passes runtime_events and never publishes here.
        self.event_queue: asyncio.Queue[DeviceEvent] = asyncio.Queue()
        self._runtime_events = runtime_events
        self._runtime_subscription = None
        
        # Tasks are started explicitly from the application's lifespan.
        self.processor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start event processing inside a running event loop."""
        if self.processor_task is None or self.processor_task.done():
            processor = self._process_runtime_events if self._runtime_events is not None else self._process_events
            self.processor_task = asyncio.create_task(processor())

    async def _process_runtime_events(self):
        """Project the sole runtime event source; do not create a second source."""
        self._runtime_subscription = self._runtime_events.subscribe()
        try:
            while True:
                try:
                    source = await asyncio.to_thread(self._runtime_subscription.get, True, 0.25)
                except Empty:
                    continue
                event = DeviceEvent(
                    device=DeviceId(device_type=DeviceType.NETWORK),
                    event_type=EventType.HARDWARE_EVENT,
                    data={
                        "sequence": source.sequence,
                        "binding_id": source.binding_id,
                        "previous": getattr(source.previous, "value", source.previous),
                        "state": getattr(source.state, "value", source.state),
                        "code": source.code,
                    },
                )
                await self._broadcast_event(event)
                await self._notify_subscribers(event)
        finally:
            if self._runtime_subscription is not None:
                self._runtime_events.unsubscribe(self._runtime_subscription)
                self._runtime_subscription = None
        
    async def connect(self, websocket: WebSocket):
        """Register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining connections: {len(self.active_connections)}")
    
    async def publish_event(self, event: DeviceEvent):
        """
        Publish a device event to be processed asynchronously.
        This is the main method that device managers should call to send events.
        """
        await self.event_queue.put(event)
        logger.debug(f"Event queued: {event.event_type} for {event.device.device_type}")
    
    async def _process_events(self):
        """Process events from the queue and distribute them to subscribers"""
        while True:
            try:
                event = await self.event_queue.get()
                logger.debug(f"Processing event: {event.event_type} for {event.device.device_type}")
                
                # Broadcast to WebSocket connections
                await self._broadcast_event(event)
                
                # Notify event subscribers
                await self._notify_subscribers(event)
                
                # Mark the task as done
                self.event_queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def _broadcast_event(self, event: DeviceEvent):
        """Broadcast an event to all active WebSocket connections"""
        if not self.active_connections:
            return
            
        dead_connections = set()
        event_json = event.to_json()
        
        for websocket in self.active_connections:
            try:
                await websocket.send_text(event_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                dead_connections.add(websocket)
        
        # Remove dead connections
        for dead_connection in dead_connections:
            self.active_connections.discard(dead_connection)
    
    async def _notify_subscribers(self, event: DeviceEvent):
        """Notify registered callback functions for this device and event type"""
        device_type = event.device.device_type
        event_type = event.event_type
        
        # Get subscribers for this device type and event type
        subscribers = self.event_subscribers.get(device_type, {}).get(event_type, [])
        
        # Also get subscribers for ALL device types but this event type
        all_device_subscribers = self.event_subscribers.get("all", {}).get(event_type, [])
        
        # Combine both lists
        all_subscribers = subscribers + all_device_subscribers
        
        # Notify all subscribers
        for subscriber in all_subscribers:
            try:
                await subscriber(event)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    def subscribe(self, device_type: DeviceType, event_type: EventType, callback: Callable[[DeviceEvent], Awaitable[None]]):
        """
        Subscribe to events for a specific device type and event type.
        Returns a function that can be called to unsubscribe.
        """
        if device_type not in self.event_subscribers:
            self.event_subscribers[device_type] = {}
        
        if event_type not in self.event_subscribers[device_type]:
            self.event_subscribers[device_type][event_type] = []
        
        self.event_subscribers[device_type][event_type].append(callback)
        logger.info(f"Added subscriber for {device_type} - {event_type}")
        
        # Return an unsubscribe function
        def unsubscribe():
            if callback in self.event_subscribers.get(device_type, {}).get(event_type, []):
                self.event_subscribers[device_type][event_type].remove(callback)
                logger.info(f"Removed subscriber for {device_type} - {event_type}")
        
        return unsubscribe
    
    async def shutdown(self):
        """Shut down the event manager"""
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
            self.processor_task = None
        self.active_connections.clear()
        logger.info("EventManager shut down")
