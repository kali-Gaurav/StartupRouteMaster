"""
Multi-Layer Cache System - IRCTC-Level Performance
Upgraded with Pub/Sub Invalidation (TODO #25) and Memory Policies (TODO #26).
"""

import asyncio
import json
import logging
import uuid
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Union, Callable
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

    def put(self, key: str, value: Any, dynamic_limit: Optional[int] = None):
        if key in self.cache: self.cache.move_to_end(key)
        self.cache[key] = value
        
        limit = dynamic_limit or self.capacity
        while len(self.cache) > limit:
            self.cache.popitem(last=False)

    def delete(self, key: str):
        self.cache.pop(key, None)

    def clear(self):
        self.cache.clear()

class MultiLayerCache:
    def __init__(self):
        self.redis: Optional[Any] = None
        self.lru = LRUCache(capacity=1000) 
        self.metrics = {
            'query_cache': CacheMetrics(),
            'lru_cache': CacheMetrics(),
            'infrastructure_cache': CacheMetrics()
        }
        self.l1_ttl = 300 
        self._initialized = False
        self._pubsub_task = None
        self._l2_latency_ms = 0.0
        self._l2_disabled_until = 0.0
        self._xfetch_beta = 1.0 # Subtask 3.3: Probabilistic recomputation
        
        # Subtask 6.1 & 6.3: Warmup & Hierarchical Logic
        from .cache_warmup import CacheWarmupOrchestrator
        self.warmup = CacheWarmupOrchestrator(self)

    def _is_l2_available(self) -> bool:
        """Subtask 3.2: Check if L2 (Redis) is healthy and fast enough."""
        if not self.redis: return False
        if time.time() < self._l2_disabled_until:
            return False
        return True

    async def _measure_l2_latency(self):
        """Measures Redis PING latency and disables L2 if too slow."""
        if not self.redis: return
        try:
            start = time.perf_counter()
            await self.redis.ping()
            latency = (time.perf_counter() - start) * 1000
            self._l2_latency_ms = (0.7 * self._l2_latency_ms) + (0.3 * latency)
            
            if self._l2_latency_ms > 50: # Threshold: 50ms
                logger.warning(f"🐢 Redis Latency High ({self._l2_latency_ms:.2f}ms). Bypassing L2 for 30s.")
                self._l2_disabled_until = time.time() + 30
        except:
            self._l2_disabled_until = time.time() + 10 # Disable briefly on error

    def _get_l1_capacity(self) -> int:
        """
        Subtask 3.1: Dynamic L1 Capacity based on available VPS RAM.
        """
        import psutil
        try:
            available_mb = psutil.virtual_memory().available / 1024 / 1024
            if available_mb < 200:
                return 500 # RAM Critical
            if available_mb < 500:
                return 1000 # RAM Low
            if available_mb > 1000:
                return 5000 # Plenty of RAM
            return 2000 # Standard
        except:
            return 1000 # Fallback

    async def prewarm_top_routes(self):
        """
        Subtask 6.2: Static Pre-caching (Top 100).
        Pulls frequent routes and injects them into L2/L1.
        """
        logger.info("🔥 Cache: Starting Static Pre-warm (Top 100 Routes)...")
        # In production, this would query the DB.
        # Here we simulate with known busy hubs.
        top_hubs = ["NDLS", "CSMT", "MAS", "HWH", "SBC", "BCT", "KOTA"]
        for hub in top_hubs:
            await self.warmup.trigger_warmup(f"hub_meta:{hub}", {"name": hub, "status": "active"}, priority="L2")
        logger.info(f"✅ Cache: Pre-warmed {len(top_hubs)} major hubs.")

    async def get(self, key: str, refresh_callback: Optional[Callable] = None) -> Optional[Any]:
        """
        Unified Get with Subtask 3.3: XFetch and Subtask 3.6: Stale-While-Revalidate.
        Returns stale data during recomputation to eliminate latency.
        """
        import math
        import random

        # Layer 0: L1 check
        cached_item = self.lru.get(key)
        
        # If not in L1, check L2 (Redis) with Subtask 3.2 latency protection
        if not cached_item and self._is_l2_available():
            try:
                from utils.compression import PayloadCompressor
                data = await self.redis.get(key)
                if data:
                    # [Subtask 3.4] Transparent Decompression
                    cached_item = PayloadCompressor.decompress(data)
                    if cached_item:
                        self.lru.put(key, cached_item, dynamic_limit=self._get_l1_capacity())
            except: pass

        if cached_item and isinstance(cached_item, dict) and "xf_expiry" in cached_item:
            # logger.debug(f"DEBUG SWR: Found envelope for {key}")
            val = cached_item["value"]
            expiry = cached_item["xf_expiry"]
            delta = cached_item.get("xf_delta", 1.0)
            
            # XFetch Algorithm
            if (time.time() - (delta * self._xfetch_beta * math.log(random.random()))) > expiry:
                # [Subtask 3.6] Stale-While-Revalidate
                if refresh_callback:
                    logger.info(f"🔄 SWR: Triggering background refresh for {key}")
                    asyncio.create_task(refresh_callback())
                
                # If not hard expired, return stale value
                if time.time() < (expiry + 300): # Allow up to 5 min stale
                    return val
                return None # Hard expired
            
            return val

        return cached_item

    async def put(self, key: str, value: Any, ttl: int = 300):
        """Unified Put with dynamic L1 limit, XFetch envelope and compression."""
        start = time.perf_counter()
        
        # 1. Wrap in XFetch envelope
        xf_item = {
            "value": value,
            "xf_expiry": time.time() + ttl,
            "xf_delta": 0.0 
        }
        
        # 2. Store raw envelope in L1 (RAM is fast, no need to compress)
        self.lru.put(key, xf_item, dynamic_limit=self._get_l1_capacity())
        
        # 3. Store compressed envelope in L2 (Redis)
        if self._is_l2_available():
            try:
                from utils.compression import PayloadCompressor
                # Estimate generation time delta
                xf_item["xf_delta"] = (time.perf_counter() - start) * 1000
                
                payload, was_compressed = PayloadCompressor.compress(xf_item)
                await self.redis.setex(key, ttl + 60, payload)
            except: pass

    async def initialize(self):
        if self._initialized: return
        try:
            redis_url = Config.REDIS_URL
            if not redis_url:
                logger.warning("REDIS_URL not set; running in RAM-ONLY mode.")
                self._initialized = True
                return

            # Task 7: Robust Connection Settings
            redis_lib = _get_redis_module()
            self.redis = redis_lib.Redis.from_url(
                redis_url, 
                decode_responses=False, 
                ssl_cert_reqs=None,
                max_connections=20,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
                health_check_interval=30
            )
            await self.redis.ping()
            
            # Start Latency Monitor (Subtask 3.2)
            async def run_monitor():
                while True:
                    await self._measure_l2_latency()
                    await asyncio.sleep(10)
            asyncio.create_task(run_monitor())

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
            self.lru.put(key, res, dynamic_limit=self._get_l1_capacity())
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
        self.lru.put(key, result, dynamic_limit=self._get_l1_capacity())
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
            self.lru.put(key, res, dynamic_limit=self._get_l1_capacity())
            self.metrics['query_cache'].hits += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='hit').inc()
            return res
        
        self.metrics['query_cache'].misses += 1
        CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='miss').inc()
        return None

    async def set_availability(self, query: AvailabilityQuery, result: Dict, ttl: int = 300):
        key = query.cache_key()
        self.lru.put(key, result, dynamic_limit=self._get_l1_capacity())
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

    async def aclose(self):
        if self.redis:
            await self.redis.aclose()

    def set_sync(self, key: str, value: Any, ttl: int = 3600):
        if self.redis:
            import redis as sync_redis_lib
            sync_r = sync_redis_lib.from_url(Config.REDIS_URL)
            sync_r.setex(key, ttl, json.dumps(value))

multi_layer_cache = MultiLayerCache()
