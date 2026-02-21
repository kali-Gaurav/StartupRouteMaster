from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Set, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    """
    Manages WebSocket connections and groups (train subscriptions).
    Phase 12: WebSocket Infrastructure for Real-time Streaming.
    """
    def __init__(self):
        # Maps user_id/websocket -> set of train numbers
        self.active_connections: Set[WebSocket] = set()
        # Maps train_number -> list of interested websockets
        self.train_subscriptions: Dict[str, List[WebSocket]] = {}
        # Global SOS listeners
        self.sos_listeners: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        # Cleanup subscriptions
        for train, subs in list(self.train_subscriptions.items()):
            if websocket in subs:
                subs.remove(websocket)
                if not subs:
                    del self.train_subscriptions[train]
        if websocket in self.sos_listeners:
            self.sos_listeners.remove(websocket)

    async def subscribe_to_train(self, websocket: WebSocket, train_number: str):
        if train_number not in self.train_subscriptions:
            self.train_subscriptions[train_number] = []
        if websocket not in self.train_subscriptions[train_number]:
            self.train_subscriptions[train_number].append(websocket)
            logger.info(f"WebSocket subscribed to train {train_number}")

    async def subscribe_to_sos(self, websocket: WebSocket):
        if websocket not in self.sos_listeners:
            self.sos_listeners.append(websocket)
            logger.info("WebSocket joined SOS responder channel")

    async def broadcast_to_train(self, train_number: str, data: Dict):
        if train_number in self.train_subscriptions:
            dead_connections = []
            for connection in self.train_subscriptions[train_number]:
                try:
                    await connection.send_json({"type": "position_update", "data": data})
                except Exception:
                    dead_connections.append(connection)
            
            for dead in dead_connections:
                self.disconnect(dead)

    async def broadcast_sos(self, data: Dict):
        dead_connections = []
        for connection in self.sos_listeners:
            try:
                await connection.send_json({"type": "sos_alert", "data": data})
            except Exception:
                dead_connections.append(connection)
        
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

@router.websocket("/ws/train/{train_number}")
async def train_websocket_endpoint(websocket: WebSocket, train_number: str):
    """Endpoint for receiving live interpolated train positions."""
    await manager.connect(websocket)
    await manager.subscribe_to_train(websocket, train_number)
    try:
        while True:
            # Keep alive and listen for control messages if any
            data = await websocket.receive_json()
            # Handle client-to-server messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS Error for {train_number}: {e}")
        manager.disconnect(websocket)

@router.websocket("/ws/sos")
async def sos_websocket_endpoint(websocket: WebSocket):
    """Endpoint for emergency responders to receive SOS alerts."""
    await manager.connect(websocket)
    await manager.subscribe_to_sos(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
