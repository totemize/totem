from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import asyncio
import logging

from service.models import DeviceCommand, DeviceState, DeviceEvent, DeviceId, EventType
from service.event_manager import EventManager

logger = logging.getLogger(__name__)


class DeviceService(ABC):
    """
    Abstract base class for all device services.
    Each type of device (display, NFC, storage, network) should implement this interface.
    """
    
    def __init__(self, device_type: str):
        self.device_type = device_type
        self.event_manager = EventManager.get_instance()
        self.device_states: Dict[str, DeviceState] = {}
        
        # Command queue for asynchronous command processing
        self.command_queue: asyncio.Queue[DeviceCommand] = asyncio.Queue()
        
        # Start the command processor
        self.command_processor_task = asyncio.create_task(self._process_commands())
    
    @abstractmethod
    async def initialize(self):
        """Initialize the device service and detect available devices"""
        pass
    
    @abstractmethod
    async def get_device_state(self, device_id: str) -> DeviceState:
        """Get the current state of a device"""
        pass
    
    @abstractmethod
    async def execute_command(self, command: DeviceCommand) -> bool:
        """Execute a command on the device"""
        pass
    
    async def queue_command(self, command: DeviceCommand) -> bool:
        """Queue a command for asynchronous execution"""
        try:
            await self.command_queue.put(command)
            logger.debug(f"Command queued: {command.command} for {self.device_type}/{command.device.device_id}")
            return True
        except Exception as e:
            logger.error(f"Error queueing command: {e}")
            return False
    
    async def _process_commands(self):
        """Process commands from the queue"""
        while True:
            try:
                command = await self.command_queue.get()
                logger.debug(f"Processing command: {command.command}")
                
                # Publish command received event
                await self.publish_event(
                    command.device.device_id, 
                    EventType.COMMAND_COMPLETED,
                    {
                        "command": command.command,
                        "status": "processing",
                        "parameters": command.parameters
                    }
                )
                
                # Execute the command
                try:
                    success = await self.execute_command(command)
                    
                    # Publish command completed event
                    await self.publish_event(
                        command.device.device_id,
                        EventType.COMMAND_COMPLETED,
                        {
                            "command": command.command,
                            "status": "completed" if success else "failed",
                            "parameters": command.parameters
                        }
                    )
                except Exception as e:
                    logger.error(f"Error executing command {command.command}: {e}")
                    # Publish error event
                    await self.publish_event(
                        command.device.device_id,
                        EventType.ERROR,
                        {
                            "command": command.command,
                            "error": str(e),
                            "parameters": command.parameters
                        }
                    )
                
                # Mark the command as processed
                self.command_queue.task_done()
            except Exception as e:
                logger.error(f"Error in command processor: {e}")
    
    async def publish_event(self, device_id: str, event_type: EventType, data: Dict[str, Any]):
        """Publish an event via the EventManager"""
        device = DeviceId(device_type=self.device_type, device_id=device_id)
        event = DeviceEvent(device=device, event_type=event_type, data=data)
        await self.event_manager.publish_event(event)
    
    async def update_device_state(self, device_id: str, state_updates: Dict[str, Any]):
        """Update device state and publish the state change event"""
        # Get or create the device state
        if device_id not in self.device_states:
            device = DeviceId(device_type=self.device_type, device_id=device_id)
            self.device_states[device_id] = DeviceState(device=device)
        
        # Update the state
        self.device_states[device_id].state.update(state_updates)
        
        # Publish state change event
        await self.publish_event(
            device_id,
            EventType.STATE_CHANGE,
            self.device_states[device_id].state
        )
        
        return self.device_states[device_id]
    
    def shutdown(self):
        """Shut down the device service"""
        if self.command_processor_task:
            self.command_processor_task.cancel()
        logger.info(f"{self.device_type.capitalize()} device service shut down") 