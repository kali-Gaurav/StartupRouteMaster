from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Set, Optional
import asyncio
import json
import logging
from backend.database.config import Config
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    """
    Distributed WebSocket Manager using Redis Pub/Sub.
    Phase 13: Redis Performance & Distributed Streaming Layer.
    """
    def __init__(self):
        # Maps user_id/websocket -> set of train numbers
        self.active_connections: Set[WebSocket] = set()
        # Maps train_number -> list of interested websockets
        self.train_subscriptions: Dict[str, List[WebSocket]] = {}
        # Global SOS listeners
        self.sos_listeners: List[WebSocket] = []
        
        # Redis Pub/Sub components
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self._pubsub_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize Redis Pub/Sub listener."""
        if self.redis:
            return
            
        try:
            self.redis = aioredis.from_url(Config.REDIS_URL, decode_responses=True)
            self.pubsub = self.redis.pubsub()
            
            # Subscribe to global channels
            await self.pubsub.subscribe("sos_alerts")
            # We will dynamically subscribe to train channels as needed or listen to a pattern
            await self.pubsub.psubscribe("train_position:*")
            
            self._pubsub_task = asyncio.create_task(self._redis_listener())
            logger.info("✅ Distributed WebSocket Manager (Redis Pub/Sub) Initialized")
        except Exception as e:
            logger.error(f"❌ Redis PubSub Initialization Failed: {e}")

    async def _redis_listener(self):
        """Background task to listen for messages from other instances via Redis."""
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    channel = message['channel']
                    payload = json.loads(message['data'])
                    
                    if channel == "sos_alerts":
                        await self._local_broadcast_sos(payload)
                    elif channel.startswith("train_position:"):
                        train_no = channel.split(":")[1]
                        await self._local_broadcast_to_train(train_no, payload)
                
                await asyncio.sleep(0.01) # Low latency check
            except Exception as e:
                logger.error(f"Redis Listener Error: {e}")
                await asyncio.sleep(1)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        # Ensure Redis is initialized
        if not self.redis:
            await self.initialize()

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
            logger.info(f"Local WebSocket subscribed to train {train_number}")

    async def subscribe_to_sos(self, websocket: WebSocket):
        if websocket not in self.sos_listeners:
            self.sos_listeners.append(websocket)
            logger.info("Local WebSocket joined SOS responder channel")

    async def broadcast_to_train(self, train_number: str, data: Dict):
        """Publishes to Redis for distributed broadcasting."""
        if not self.redis:
            await self.initialize()
            
        if self.redis:
            try:
                await self.redis.publish(f"train_position:{train_number}", json.dumps(data))
            except Exception as e:
                logger.error(f"Redis Publish Error: {e}")
                await self._local_broadcast_to_train(train_number, data)
        else:
            # Fallback to local if Redis is down
            await self._local_broadcast_to_train(train_number, data)

    async def broadcast_sos(self, data: Dict):
        """Publishes to Redis for distributed broadcasting."""
        if not self.redis:
            await self.initialize()
            
        if self.redis:
            try:
                await self.redis.publish("sos_alerts", json.dumps(data))
            except Exception as e:
                logger.error(f"Redis SOS Publish Error: {e}")
                await self._local_broadcast_sos(data)
        else:
            # Fallback to local
            await self._local_broadcast_sos(data)

    async def _local_broadcast_to_train(self, train_number: str, data: Dict):
        """Sends to only locally connected clients."""
        if train_number in self.train_subscriptions:
            dead_connections = []
            for connection in self.train_subscriptions[train_number]:
                try:
                    await connection.send_json({"type": "position_update", "data": data})
                except Exception:
                    dead_connections.append(connection)
            
            for dead in dead_connections:
                self.disconnect(dead)

    async def _local_broadcast_sos(self, data: Dict):
        """Sends to only locally connected emergency responders."""
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
            # Keep alive and handle client pings
            await websocket.receive_text()
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
