import json
import logging
import asyncio
import uuid
from typing import Dict, Any, Callable, Awaitable
from services.multi_layer_cache import multi_layer_cache, PROCESS_ID

logger = logging.getLogger(__name__)

class PlatformEventBus:
    """
    Subtask 30.1: Multi-Node Event Broadcasting.
    Uses Redis Pub/Sub to synchronize state and signals across all backend workers.
    """
    def __init__(self):
        self.handlers: Dict[str, Callable[[Dict], Awaitable[None]]] = {}
        self._listener_task = None

    async def initialize(self):
        """Starts the background listener for cross-node events."""
        await multi_layer_cache.initialize()
        if not multi_layer_cache.redis:
            logger.warning("Redis unavailable. Cross-node events disabled.")
            return
            
        self._listener_task = asyncio.create_task(self._listen())
        logger.info(f"Platform Event Bus Initialized (Node: {PROCESS_ID})")

    def subscribe(self, event_type: str, handler: Callable[[Dict], Awaitable[None]]):
        """Registers a handler for a specific event type."""
        self.handlers[event_type] = handler

    async def broadcast(self, event_type: str, payload: Dict[str, Any]):
        """Publishes an event to all active nodes in the cluster."""
        if not multi_layer_cache.redis: return
        
        envelope = {
            "sender": PROCESS_ID,
            "type": event_type,
            "payload": payload,
            "timestamp": json.dumps(datetime.utcnow(), default=str)
        }
        
        await multi_layer_cache.redis.publish("platform:events", json.dumps(envelope))

    async def _listen(self):
        """Background loop to process incoming cluster signals."""
        pubsub = multi_layer_cache.redis.pubsub()
        await pubsub.subscribe("platform:events")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'].decode('utf-8'))
                    if data.get('sender') == PROCESS_ID: continue # Ignore self
                    
                    event_type = data.get('type')
                    if event_type in self.handlers:
                        await self.handlers[event_type](data.get('payload'))
                        logger.info(f"Cluster Signal Received: {event_type} from {data.get('sender')}")
                except Exception as e:
                    logger.error(f"Event Bus Error: {e}")

from datetime import datetime
platform_bus = PlatformEventBus()
