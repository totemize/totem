import asyncio
import logging
from typing import Dict, List, Set, Callable, Awaitable, Any, Optional
from fastapi import WebSocket
import json

from service.models import DeviceEvent, DeviceId, DeviceType, EventType

logger = logging.getLogger(__name__)


class EventManager:
    """
    EventManager handles broadcasting device events to WebSocket clients and event subscribers.
    It also provides methods for device managers to publish events.
    """
    _instance: Optional['EventManager'] = None
    
    @classmethod
    def get_instance(cls) -> 'EventManager':
        """Get the singleton instance of EventManager"""
        if cls._instance is None:
            cls._instance = EventManager()
        return cls._instance
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Event subscribers (callbacks) by device type and event type
        self.event_subscribers: Dict[DeviceType, Dict[EventType, List[Callable[[DeviceEvent], Awaitable[None]]]]] = {
            device_type: {event_type: [] for event_type in EventType} 
            for device_type in DeviceType
        }
        
        # Create an event loop
        self.loop = asyncio.get_event_loop()
        
        # Event queue
        self.event_queue: asyncio.Queue[DeviceEvent] = asyncio.Queue()
        
        # Start the event processor
        self.processor_task = asyncio.create_task(self._process_events())
        
    async def connect(self, websocket: WebSocket):
        """Register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.remove(websocket)
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
            self.active_connections.remove(dead_connection)
    
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
    
    def shutdown(self):
        """Shut down the event manager"""
        if self.processor_task:
            self.processor_task.cancel()
        logger.info("EventManager shut down") 