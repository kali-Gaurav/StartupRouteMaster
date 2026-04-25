import time
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from core.system_monitor import SystemState

logger = logging.getLogger("routemaster.discovery")

class ServiceRegistry:
    """
    Task 7.6: Redis-based Service Discovery Registry.
    Handles registration, health heartbeats, and service lookups.
    """
    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "discovery:service:"
        self._local_cache = {} # Cache for fast lookups
        self._last_refresh = 0

    async def register(self, name: str, node_id: str, host: str, port: int, metadata: Optional[Dict] = None):
        """Registers a service node with a TTL."""
        key = f"{self.prefix}{name}:{node_id}"
        data = {
            "name": name,
            "node_id": node_id,
            "host": host,
            "port": port,
            "status": "healthy",
            "last_seen": time.time(),
            "metadata": metadata or {}
        }
    async def heartbeat_update(self, name: str, node_id: str, metadata: Dict[str, Any]):
        """
        [Task 4.6] Lightweight heartbeat to update node metrics (Load/CPU).
        """
        key = f"{self.prefix}{name}:{node_id}"
        existing = await self.redis.get(key)
        if existing:
            data = json.loads(existing)
            data["last_seen"] = time.time()
            data["metadata"].update(metadata)
            await self.redis.setex(key, 30, json.dumps(data))
        else:
            logger.warning(f"⚠️ Heartbeat for unknown node {node_id}. Re-registering.")

    async def get_nodes(self, name: str) -> List[Dict[str, Any]]:
        """
        Returns all healthy nodes for a given service.
        Includes 1s local cache to prevent Redis bottlenecks.
        """
        now = time.time()
        if name in self._local_cache:
            cache_time, nodes = self._local_cache[name]
            if now - cache_time < 1.0: # 1s TTL
                return nodes

        keys = await self.redis.keys(f"{self.prefix}{name}:*")
        nodes = []
        for key in keys:
            data = await self.redis.get(key)
            if data:
                nodes.append(json.loads(data))
        
        self._local_cache[name] = (now, nodes)
        return nodes

    async def resolve_endpoint(self, name: str) -> Optional[str]:
        """Simple Round-Robin / Load-Balanced selection of a node."""
        nodes = await self.get_nodes(name)
        if not nodes:
            return None
        
        # Simple random selection for now (can be upgraded to Least Connections)
        import random
        selected = random.choice(nodes)
        return f"http://{selected['host']}:{selected['port']}"

service_registry = None # To be initialized with Redis
