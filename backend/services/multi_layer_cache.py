"""
Multi-Layer Cache System - IRCTC-Level Performance
Upgraded with Pub/Sub Invalidation (TODO #25) and Memory Policies (TODO #26).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from dataclasses import dataclass, asdict
from collections import OrderedDict
import hashlib
import pickle
import zlib

from database.config import Config
from database.session import SessionLocal

_redis_lib = None

def _get_redis_module():
    """Lazily import redis.asyncio to avoid startup overhead when Redis isn't used."""
    global _redis_lib
    if _redis_lib is None:
        import redis.asyncio as redis
        _redis_lib = redis
    return _redis_lib

logger = logging.getLogger(__name__)

# Unique ID for this process instance to avoid self-invalidation loops
PROCESS_ID = str(uuid.uuid4())[:8]

@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict:
        return {**asdict(self), 'hit_rate': self.hit_rate}

@dataclass
class RouteQuery:
    from_station: str
    to_station: str
    date: date
    class_preference: Optional[str] = None
    max_transfers: int = 3
    include_wait_time: bool = True

    def cache_key(self) -> str:
        key_data = f"{self.from_station}:{self.to_station}:{self.date.isoformat()}:{self.class_preference}:{self.max_transfers}:{self.include_wait_time}"
        return f"route:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

@dataclass
class AvailabilityQuery:
    train_id: int
    from_stop_id: int
    to_stop_id: int
    travel_date: date
    quota_type: str = "GN"
    class_type: str = "SL"

    def cache_key(self) -> str:
        date_str = self.travel_date.isoformat()
        return f"avail:{self.train_id}:{self.from_stop_id}:{self.to_stop_id}:{date_str}:{self.quota_type}:{self.class_type}"

class LRUCache:
    def __init__(self, capacity: int = 500):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache: return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        if key in self.cache: self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity: self.cache.popitem(last=False)

    def delete(self, key: str):
        self.cache.pop(key, None)

    def clear(self):
        self.cache.clear()

class MultiLayerCache:
    def __init__(self):
        self.redis: Optional[Any] = None
        self.lru = LRUCache(capacity=500)
        self.metrics = {
            'query_cache': CacheMetrics(),
            'lru_cache': CacheMetrics(),
            'infrastructure_cache': CacheMetrics()
        }
        self._initialized = False
        self._pubsub_task = None

    async def initialize(self):
        if self._initialized: return
        try:
            redis_url = Config.REDIS_URL
            if not redis_url:
                logger.warning("REDIS_URL not set; running in RAM-ONLY mode.")
                self._initialized = True
                return

            # Task 7: Robust Connection Settings for Cloud (Upstash/GCP/AWS)
            redis_lib = _get_redis_module()
            self.redis = redis_lib.Redis.from_url(
                redis_url, 
                decode_responses=False, 
                ssl_cert_reqs=None,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
                health_check_interval=30
            )
            await self.redis.ping()
            
            # Suggestion #26: Memory Policies
            try:
                await self.redis.config_set("maxmemory-policy", "allkeys-lru")
            except: pass

            # Task 30.2: Subscribe to Cluster Invalidation
            from services.event_bus import platform_bus
            platform_bus.subscribe("CACHE_INVALIDATE", self._handle_cluster_invalidation)
            
            logger.info(f"✅ Task 7: Multi-layer cache initialized (Instance: {PROCESS_ID})")
        except Exception as e:
            logger.error(f"❌ Task 7: Redis unavailable: {e}. Falling back to RAM-ONLY.")
            self.redis = None
        self._initialized = True

    async def _handle_cluster_invalidation(self, payload: Dict):
        """Callback for PlatformEventBus to clear local LRU."""
        key = payload.get("key")
        if key:
            self.lru.delete(key)
            logger.info(f"Cluster Signal: Deleted local key {key}")
        else:
            self.lru.clear()
            logger.info("Cluster Signal: Cleared local LRU")
        self.metrics['lru_cache'].deletes += 1

    async def mark_train_sold_out(self, train_no: str, date_str: str):
        if not self.redis: return
        key = f"soldout:{train_no}:{date_str}"
        await self.redis.setex(key, 3600 * 24, "1") # 24h cache

    async def is_train_sold_out(self, train_no: str, date_str: str) -> bool:
        if not self.redis: return False
        return await self.redis.exists(f"soldout:{train_no}:{date_str}")

    async def _listen_for_invalidations(self):
        """Background task to clear local LRU on Pub/Sub signal (Task 25)."""
        if not self.redis: return
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("cache:invalidation")
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'].decode('utf-8'))
                if data.get('sender') != PROCESS_ID:
                    logger.info(f"Broadcast received: Invalidating local LRU ({data.get('type')})")
                    self.lru.clear()
                    self.metrics['lru_cache'].deletes += 1

    async def get_route_query(self, query: RouteQuery) -> Optional[Dict]:
        key = query.cache_key()
        # Layer 0: Local In-Memory
        lru_data = self.lru.get(key)
        if lru_data:
            self.metrics['lru_cache'].hits += 1
            from utils.metrics import CACHE_OPERATIONS_TOTAL
            CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='hit').inc()
            return lru_data
        
        from utils.metrics import CACHE_OPERATIONS_TOTAL
        CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='miss').inc()

        if not self.redis: return None
        
        # Layer 1: Redis Infrastructure
        data = await self.redis.get(key)
        if data:
            res = json.loads(data.decode('utf-8'))
            self.lru.put(key, res)
            self.metrics['query_cache'].hits += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='hit').inc()
            return res
        
        self.metrics['query_cache'].misses += 1
        CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='miss').inc()
        return None

    def record_graph_metrics(self, nodes: int, edges: int, rebuild_time: float = None):
        """
        Subtask 11.2: Record Graph Footprint.
        Populates Prometheus gauges with graph complexity and memory stats.
        """
        from utils.metrics import GRAPH_NODES_TOTAL, GRAPH_EDGES_TOTAL, GRAPH_MEMORY_USAGE_MB, GRAPH_LAST_REBUILD_TIMESTAMP
        GRAPH_NODES_TOTAL.set(nodes)
        GRAPH_EDGES_TOTAL.set(edges)
        estimated_mb = ((nodes * 200) + (edges * 100)) / (1024 * 1024)
        GRAPH_MEMORY_USAGE_MB.set(round(estimated_mb, 2))
        if rebuild_time: GRAPH_LAST_REBUILD_TIMESTAMP.set(rebuild_time)
        logger.info(f"Graph Metrics Recorded: {nodes} nodes, {edges} edges (~{estimated_mb:.1f}MB)")

    async def set_route_query(self, query: RouteQuery, result: Dict, ttl_minutes: int = 5):
        key = query.cache_key()
        self.lru.put(key, result)
        from utils.metrics import CACHE_OPERATIONS_TOTAL
        CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='set', result='success').inc()
        
        if self.redis:
            await self.redis.setex(key, ttl_minutes * 60, json.dumps(result, default=str))
            self.metrics['query_cache'].sets += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='set', result='success').inc()
            await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "type": "set", "key": key}))

    async def get_availability(self, query: AvailabilityQuery) -> Optional[Dict]:
        key = query.cache_key()
        lru_data = self.lru.get(key)
        if lru_data:
            self.metrics['lru_cache'].hits += 1
            from utils.metrics import CACHE_OPERATIONS_TOTAL
            CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='hit').inc()
            return lru_data
        
        from utils.metrics import CACHE_OPERATIONS_TOTAL
        CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='miss').inc()

        if not self.redis: return None
        data = await self.redis.get(key)
        if data:
            res = json.loads(data.decode('utf-8'))
            self.lru.put(key, res)
            self.metrics['query_cache'].hits += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='hit').inc()
            return res
        
        self.metrics['query_cache'].misses += 1
        CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='miss').inc()
        return None

    async def set_availability(self, query: AvailabilityQuery, result: Dict, ttl: int = 300):
        key = query.cache_key()
        self.lru.put(key, result)
        from utils.metrics import CACHE_OPERATIONS_TOTAL
        CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='set', result='success').inc()
        if self.redis:
            await self.redis.setex(key, ttl, json.dumps(result, default=str))
            self.metrics['query_cache'].sets += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='set', result='success').inc()

    async def get_cache_stats(self) -> Dict:
        return {k: v.to_dict() for k, v in self.metrics.items()}

    async def get_many(self, keys: List[str]) -> List[Optional[Dict]]:
        if not self.redis or not keys: return [None] * len(keys)
        try:
            values = await self.redis.mget(keys)
            return [json.loads(val.decode('utf-8')) if val else None for val in values]
        except Exception: return [None] * len(keys)

    async def set_many(self, mapping: Dict[str, Any], ttl: int = 3600):
        if not self.redis or not mapping: return
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                for key, value in mapping.items():
                    pipe.setex(key, ttl, json.dumps(value, default=str))
                await pipe.execute()
        except Exception: pass

    async def get_graph_snapshot(self, date_str: str) -> Optional[Any]:
        if not self.redis: return None
        key = f"graph:snapshot:{date_str}"
        try:
            data = await self.redis.get(key)
            if data: return pickle.loads(zlib.decompress(data))
        except Exception: pass
        return None

    async def set_graph_snapshot(self, date_str: str, snapshot: Any, ttl: int = 86400):
        if not self.redis: return
        try:
            compressed = zlib.compress(pickle.dumps(snapshot, protocol=pickle.HIGHEST_PROTOCOL))
            await self.redis.setex(f"graph:snapshot:{date_str}", ttl, compressed)
            logger.info(f"✅ Saved {len(compressed)/1024/1024:.2f}MB snapshot to Redis")
        except Exception: pass

    def get_lock(self, name: str, timeout: int = 10):
        return self.redis.lock(name, timeout=timeout) if self.redis else None

    def set_sync(self, key: str, value: Any, ttl: int = 3600):
        if self.redis:
            import redis as sync_redis_lib
            sync_r = sync_redis_lib.from_url(Config.REDIS_URL)
            sync_r.setex(key, ttl, json.dumps(value))

multi_layer_cache = MultiLayerCache()
