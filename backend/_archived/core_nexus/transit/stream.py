import asyncio
import json
import logging
import asyncio
from typing import AsyncGenerator
from fastapi import Request
from sse_starlette import EventSourceResponse


from core.nexus.audit.chaos import chaos_trap

logger = logging.getLogger("nexus.transit.stream")

class NexusTransitStreamer:
    """[Task 13.10] Nexus Real-time Transit Streamer (SSE).
    Provides a high-intensity event stream for train delay reconciliation.
    """
    
    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    async def subscribe(self, request: Request) -> EventSourceResponse:
        """Subscribe a frontend client to the transit event stream."""
        queue = asyncio.Queue()
        self._queues.add(queue)
        
        logger.info(f"[NEXUS:STREAM] New Client Connected. Active: {len(self._queues)}")
        logger.debug(f"[NEXUS:STREAM] Queues ID set: {id(self._queues)}")
        
        return EventSourceResponse(self._event_generator(request, queue))

    @chaos_trap("sse_jitter")
    async def _event_generator(self, request: Request, queue: asyncio.Queue) -> AsyncGenerator[dict, None]:
        """Generates SSE events from the internal broadcast queue."""
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for data or timeout to keep connection alive
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield {
                        "event": "transit_update",
                        "id": str(asyncio.get_event_loop().time()),
                        "retry": 15000,
                        "data": json.dumps(data)
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "heartbeat"}
                    
        finally:
            self._queues.remove(queue)
            logger.info(f"[NEXUS:STREAM] Client Disconnected. Remaining: {len(self._queues)}")

    async def broadcast(self, payload: dict):
        """Broadcasts a transit update to all active subscribers."""
        logger.debug(f"[NEXUS:STREAM] Broadcast called. Queues: {len(self._queues)} | ID: {id(self._queues)}")
        if not self._queues:
            return
            
        logger.info(f"[NEXUS:STREAM] Broadcasting to {len(self._queues)} clients...")
        for queue in self._queues:
            await queue.put(payload)

# Global Streamer Instance
transit_streamer = NexusTransitStreamer()
