from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from typing import List, Dict, Set, Optional
import asyncio
import json
import logging
from jose import JWTError
from backend.database.config import Config
import redis.asyncio as aioredis
from backend.core.monitoring import WS_CONNECTIONS, WS_TRAIN_SUBSCRIPTIONS, WS_BROADCAST_ERRORS
from backend.utils.security import decode_access_token
from backend.database import SessionLocal
from backend.services.user_service import UserService

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
            try:
                await self.redis.ping()
                return
            except Exception:
                logger.warning("Redis ping failed, re-initializing...")
                self.redis = None
            
        try:
            self.redis = aioredis.from_url(
                Config.REDIS_URL, 
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True
            )
            self.pubsub = self.redis.pubsub()
            
            # Subscribe to global channels
            await self.pubsub.subscribe("sos_alerts")
            # We will dynamically subscribe to train channels as needed or listen to a pattern
            await self.pubsub.psubscribe("train_position:*")
            
            if not self._pubsub_task or self._pubsub_task.done():
                self._pubsub_task = asyncio.create_task(self._redis_listener())
            
            from backend.core.monitoring import SYSTEM_DEGRADED_MODE
            SYSTEM_DEGRADED_MODE.labels(reason="redis_failure").set(0)
            logger.info("✅ Distributed WebSocket Manager (Redis Pub/Sub) Initialized")
        except Exception as e:
            from backend.core.monitoring import REDIS_HEALTH_CHECKS, SYSTEM_DEGRADED_MODE
            REDIS_HEALTH_CHECKS.labels(status="fail").inc()
            SYSTEM_DEGRADED_MODE.labels(reason="redis_failure").set(1)
            logger.error(f"❌ Redis PubSub Initialization Failed: {e}")

    async def _redis_listener(self):
        """Background task to listen for messages from other instances via Redis."""
        while True:
            try:
                if not self.pubsub:
                    # Attempt to re-initialize if pubsub is missing
                    await asyncio.sleep(5)
                    await self.initialize()
                    continue
                    
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] in ['message', 'pmessage']:
                    # ... (rest of logic)
                    pass # Placeholder for brevity, I will match exact text in tool call
                if message and message['type'] in ['message', 'pmessage']:
                    channel = message.get('channel')
                    data = message.get('data')
                    
                    if not channel or not data:
                        continue
                        
                    payload = json.loads(data)
                    
                    if channel == "sos_alerts":
                        await self._local_broadcast_sos(payload)
                    elif channel.startswith("train_position:"):
                        train_no = channel.split(":")[1]
                        await self._local_broadcast_to_train(train_no, payload)
                
                await asyncio.sleep(0.1)
                from backend.core.monitoring import REDIS_HEALTH_CHECKS
                REDIS_HEALTH_CHECKS.labels(status="ok").inc()
            except Exception as e:
                logger.error(f"Redis Listener Error: {e}")
                from backend.core.monitoring import REDIS_HEALTH_CHECKS
                REDIS_HEALTH_CHECKS.labels(status="fail").inc()
                # If connection is lost, clear redis/pubsub so it re-initializes
                self.redis = None
                self.pubsub = None
                await asyncio.sleep(5)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        WS_CONNECTIONS.inc()
        # Ensure Redis is initialized
        if not self.redis:
            await self.initialize()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        WS_CONNECTIONS.dec()
        # Cleanup subscriptions
        for train, subs in list(self.train_subscriptions.items()):
            if websocket in subs:
                subs.remove(websocket)
                WS_TRAIN_SUBSCRIPTIONS.labels(train_number=train).dec()
                if not subs:
                    del self.train_subscriptions[train]
        if websocket in self.sos_listeners:
            self.sos_listeners.remove(websocket)

    async def subscribe_to_train(self, websocket: WebSocket, train_number: str):
        if train_number not in self.train_subscriptions:
            self.train_subscriptions[train_number] = []
        if websocket not in self.train_subscriptions[train_number]:
            self.train_subscriptions[train_number].append(websocket)
            WS_TRAIN_SUBSCRIPTIONS.labels(train_number=train_number).inc()
            logger.info(f"Local WebSocket subscribed to train {train_number}")
            
            # Phase 13: Redis State Catch-up
            try:
                if self.redis:
                    history_key = f"pos:last:{train_number}"
                    cached_pos = await self.redis.get(history_key)
                    if cached_pos:
                        await websocket.send_text(cached_pos)
                        logger.info(f"Sent 'Last Known' catch-up to new subscriber for {train_number}")
            except Exception as e:
                logger.error(f"Catch-up logic failed: {e}")

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
                    WS_BROADCAST_ERRORS.labels(type='pos').inc()
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
                WS_BROADCAST_ERRORS.labels(type='sos').inc()
                dead_connections.append(connection)
        
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

async def get_ws_user(token: str):
    """Verifies JWT and returns user object for WebSocket authentication."""
    try:
        token_data = decode_access_token(token)
        if not token_data or not token_data.email:
            return None
        
        db = SessionLocal()
        user_service = UserService(db)
        user = user_service.get_user_by_email(token_data.email) or user_service.get_user_by_phone(token_data.email)
        db.close()
        return user
    except (JWTError, Exception) as e:
        logger.error(f"WS Auth Error: {e}")
        return None

@router.websocket("/ws/train/{train_number}")
async def train_websocket_endpoint(
    websocket: WebSocket, 
    train_number: str,
    token: Optional[str] = Query(None)
):
    """Endpoint for receiving live interpolated train positions."""
    # 1. JWT Authentication
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Connection Handling
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
async def sos_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """Endpoint for emergency responders to receive SOS alerts."""
    # 1. JWT Authentication & RBAC
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    user = await get_ws_user(token)
    if not user or user.role not in ['admin', 'responder', 'support']:
        logger.warning(f"Unauthorized SOS access attempt by user: {user.email if user else 'Unknown'}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Connection Handling
    await manager.connect(websocket)
    await manager.subscribe_to_sos(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"SOS WS Error: {e}")
        manager.disconnect(websocket)
