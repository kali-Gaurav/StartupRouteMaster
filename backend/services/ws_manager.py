import logging
import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Task 31: User Real-Time Status Manager.
    Handles WS connections, Keep-Alives, and Redis Pub/Sub for scale.
    """
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.redis_client = None
        self.pubsub_task = None

    async def _redis_listener(self):
        """[31.7] Redis Pub/Sub Backbone for multi-worker broadcasting."""
        if not self.redis_client: return
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("booking_updates")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    b_id = data.get("booking_id")
                    if b_id and b_id in self.active_connections:
                        payload = data.get("payload")
                        for connection in self.active_connections[b_id]:
                            try:
                                await connection.send_json(payload)
                            except Exception:
                                pass
        except asyncio.CancelledError:
            await pubsub.unsubscribe("booking_updates")

    async def connect(self, booking_id: str, websocket: WebSocket, current_status: str = None):
        """[31.1] & [31.5] Accept connection and manage keep-alive."""
        await websocket.accept()
        if booking_id not in self.active_connections:
            self.active_connections[booking_id] = []
        self.active_connections[booking_id].append(websocket)
        logger.info(f"WebSocket connected for booking: {booking_id}")
        
        # [31.4] Fast-Sync on Reconnect
        if current_status:
            await websocket.send_json({
                "type": "sync", 
                "status": current_status, 
                "message": "Connected and synced."
            })

    def disconnect(self, booking_id: str, websocket: WebSocket):
        if booking_id in self.active_connections:
            if websocket in self.active_connections[booking_id]:
                self.active_connections[booking_id].remove(websocket)
            if not self.active_connections[booking_id]:
                del self.active_connections[booking_id]

    async def broadcast_log(self, booking_id: str, message: str, status: str = None):
        """
        [31.9] Detailed Payload Structure.
        Broadcasts a log message to all clients watching this booking (local or via Redis).
        """
        from datetime import datetime
        payload = {
            "type": "booking_log", 
            "message": message, 
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Local broadcast
        if booking_id in self.active_connections:
            for connection in self.active_connections[booking_id]:
                try:
                    await connection.send_json(payload)
                except Exception as e:
                    logger.warning(f"Failed to send WS log locally: {e}")
                    
        # Redis broadcast (if initialized)
        if self.redis_client:
            await self.redis_client.publish(
                "booking_updates", 
                json.dumps({"booking_id": booking_id, "payload": payload})
            )

    async def setup_redis(self, redis_client):
        self.redis_client = redis_client
        if self.pubsub_task is None:
            self.pubsub_task = asyncio.create_task(self._redis_listener())

# Singleton instance
ws_manager = ConnectionManager()
