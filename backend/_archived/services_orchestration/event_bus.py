"""
Event Bus Service - Multi-Node Event Broadcasting
==================================================

Uses Redis Pub/Sub to synchronize state and signals across all backend workers.
Provides reliable event distribution with circuit breaker protection.

With resilience patterns: circuit breaker, retry, metrics tracking, and comprehensive error handling.

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

import json
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Awaitable, Optional, List
from services.multi_layer_cache import multi_layer_cache, PROCESS_ID
from core.resilience.core import circuit_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy
from collections import deque
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Event structure for the bus."""
    event_id: str
    sender: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime


class PlatformEventBus:
    """
    Subtask 30.1: Multi-Node Event Broadcasting.
    Uses Redis Pub/Sub to synchronize state and signals across all backend workers.
    
    With resilience patterns: circuit breaker, retry, metrics tracking, and health checks.
    """
    
    def __init__(self):
        """Initialize event bus with resilience patterns."""
        self.handlers: Dict[str, Callable[[Dict], Awaitable[None]]] = {}
        self._listener_task = None
        
        # Circuit breaker for Redis operations
        self._redis_breaker = circuit_manager.get_or_create(
            "event_bus_redis",
            CircuitConfig(
                failure_threshold=5,
                timeout_seconds=30.0,
                success_threshold=3
            )
        )
        
        # Retry policy for operations
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=2.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        # Event history
        self._event_history: deque = deque(maxlen=1000)
        self._history_lock = asyncio.Lock()
        
        # Subscription tracking
        self._subscriptions: Dict[str, int] = {}
        self._subscriptions_lock = asyncio.Lock()
        
        logger.info("PlatformEventBus initialized with resilience patterns")

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
        
        # Track subscription
        self._subscriptions[event_type] = self._subscriptions.get(event_type, 0) + 1
        
        logger.info(f"📝 Subscribed to event type: {event_type}")

    def unsubscribe(self, event_type: str):
        """Unregisters handler for a specific event type."""
        if event_type in self.handlers:
            del self.handlers[event_type]
            self._subscriptions[event_type] = max(0, self._subscriptions.get(event_type, 0) - 1)
            logger.info(f"📝 Unsubscribed from event type: {event_type}")

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """
        Publishes an event to all active nodes in the cluster.
        
        Args:
            event_type: Type of event
            payload: Event payload
            
        Returns:
            True if published successfully, False otherwise
        """
        if not multi_layer_cache.redis:
            logger.warning("⚠️ Redis unavailable. Event not broadcast.")
            return False
        
        envelope = {
            "event_id": str(uuid.uuid4()),
            "sender": PROCESS_ID,
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async def _publish():
            """Internal publish logic."""
            await multi_layer_cache.redis.publish(
                "platform:events",
                json.dumps(envelope)
            )
        
        try:
            await self._redis_breaker.execute(
                self._retry_policy.execute,
                _publish
            )
            
            # Record metrics
            await self._record_metrics("broadcast", True, event_type)
            
            # Add to history
            await self._add_to_history(envelope)
            
            logger.debug(f"📡 Broadcast event: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Broadcast failed for {event_type}: {e}")
            await self._record_metrics("broadcast", False, event_type)
            return False

    async def _listen(self):
        """Background loop to process incoming cluster signals."""
        if not multi_layer_cache.redis:
            logger.warning("Redis unavailable. Event bus listener cannot start.")
            return

        pubsub = multi_layer_cache.redis.pubsub()
        await pubsub.subscribe("platform:events")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'].decode('utf-8'))
                    if data.get('sender') == PROCESS_ID:
                        continue  # Ignore self
                    
                    event_type = data.get('type')
                    if event_type in self.handlers:
                        await self.handlers[event_type](data.get('payload'))
                        logger.info(
                            f"Cluster Signal Received: {event_type} from {data.get('sender')}"
                        )
                        
                        # Record metrics
                        await self._record_metrics("receive", True, event_type)
                    else:
                        logger.debug(f"📥 Received unhandled event: {event_type}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Invalid JSON in event: {e}")
                except Exception as e:
                    logger.error(f"Event Bus Error: {e}")
                    await self._record_metrics("receive", False, "unknown")

    async def send_direct(
        self,
        target_node: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Send event to a specific node.
        
        Args:
            target_node: Target node ID
            event_type: Type of event
            payload: Event payload
            
        Returns:
            True if sent successfully
        """
        envelope = {
            "event_id": str(uuid.uuid4()),
            "sender": PROCESS_ID,
            "target": target_node,
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis for target node to pick up
        if multi_layer_cache.redis:
            try:
                key = f"direct_events:{target_node}"
                await multi_layer_cache.redis.lpush(key, json.dumps(envelope))
                await multi_layer_cache.redis.expire(key, 300)  # 5 min TTL
                return True
            except Exception as e:
                logger.error(f"❌ Direct send failed: {e}")
                return False
        
        return False

    async def get_pending_events(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get pending direct events for a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            List of pending events
        """
        if not multi_layer_cache.redis:
            return []
        
        try:
            key = f"direct_events:{node_id}"
            events = await multi_layer_cache.redis.lrange(key, 0, -1)
            return [json.loads(e.decode('utf-8')) for e in events]
        except Exception as e:
            logger.error(f"❌ Failed to get pending events: {e}")
            return []

    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    async def _record_metrics(
        self,
        operation_type: str,
        success: bool,
        event_type: str = ""
    ):
        """Record operation metrics for monitoring."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "event_type": event_type
            })

    async def _add_to_history(self, envelope: Dict[str, Any]):
        """Add event to history."""
        async with self._history_lock:
            self._event_history.append({
                "event_id": envelope.get("event_id"),
                "type": envelope.get("type"),
                "sender": envelope.get("sender"),
                "timestamp": envelope.get("timestamp")
            })

    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_events": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            e_type = m.get("event_type", "unknown")
            by_type[e_type] = by_type.get(e_type, 0) + 1
        
        return {
            "total_events": total,
            "successful_events": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "event_breakdown": by_type,
            "active_subscriptions": len(self.handlers),
            "circuit_breaker_state": self._redis_breaker.get_state().value
        }

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "redis_available": multi_layer_cache.redis is not None,
            "listener_running": self._listener_task is not None and not self._listener_task.done(),
            "circuit_breaker": {
                "state": self._redis_breaker.get_state().value,
                "failure_count": self._redis_breaker.failure_count,
                "success_count": self._redis_breaker.success_count
            },
            "metrics": self.get_metrics()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._redis_breaker.reset()
        logger.info("Circuit breaker reset for event bus")

    def get_event_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent event history."""
        return list(self._event_history)[-limit:]

    def get_subscriptions(self) -> Dict[str, int]:
        """Get subscription counts by event type."""
        return dict(self._subscriptions)


# Global instance
platform_bus = PlatformEventBus()
