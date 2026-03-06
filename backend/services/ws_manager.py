import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Task 42: WebSocket Log Streaming Manager.
    """
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, booking_id: str, websocket: WebSocket):
        await websocket.accept()
        if booking_id not in self.active_connections:
            self.active_connections[booking_id] = []
        self.active_connections[booking_id].append(websocket)
        logger.info(f"WebSocket connected for booking: {booking_id}")

    def disconnect(self, booking_id: str, websocket: WebSocket):
        if booking_id in self.active_connections:
            self.active_connections[booking_id].remove(websocket)
            if not self.active_connections[booking_id]:
                del self.active_connections[booking_id]

    async def broadcast_log(self, booking_id: str, message: str, status: str = None):
        """Broadcasts a log message to all clients watching this booking."""
        if booking_id in self.active_connections:
            payload = {"type": "booking_log", "message": message, "status": status}
            for connection in self.active_connections[booking_id]:
                try:
                    await connection.send_json(payload)
                except Exception as e:
                    logger.warning(f"Failed to send WS log: {e}")

# Singleton instance
ws_manager = ConnectionManager()
