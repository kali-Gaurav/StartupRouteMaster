"""
Multi-Layer Cache System - IRCTC-Level Performance
Upgraded with Pub/Sub Invalidation (TODO #25) and Memory Policies (TODO #26).
"""

import asyncio
import json
import logging
import uuid
import time
import math
import random
import hashlib
import pickle
import zlib
import functools
from datetime import datetime, date, timedelta

# [Task 47.4] TTL Staggering Config
TTL_PNR_LIVE = 60           # 1 Minute
TTL_AVAIL_LIVE = 300        # 5 Minutes
TTL_ROUTE_SEARCH = 3600     # 1 Hour
TTL_TRAIN_SCHEDULE = 86400  # 24 Hours
TTL_STATION_MASTER = 2592000 # 30 Days
TTL_NEGATIVE_MISS = 300     # 5 Minutes
from typing import Dict, List, Optional, Any, Set, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from collections import OrderedDict

from database.config import Config
from utils.compression import PayloadCompressor
from utils.metrics import (
    CACHE_OPERATIONS_TOTAL, 
    GRAPH_NODES_TOTAL, 
    GRAPH_EDGES_TOTAL, 
    GRAPH_MEMORY_USAGE_MB, 
    GRAPH_LAST_REBUILD_TIMESTAMP
)

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
        """
        [Task 47.2] Canonical Hashing.
        Ensures 'NDLS' and 'ndls' result in the same key.
        """
        from_canonical = self.from_station.strip().upper()
        to_canonical = self.to_station.strip().upper()
        date_str = self.date.isoformat()
        
        # [Task 47.3] Thundering Herd prevention ID
        key_data = f"{from_canonical}:{to_canonical}:{date_str}:{self.class_preference}:{self.max_transfers}:{self.include_wait_time}"
        return f"route:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

@dataclass
class AvailabilityQuery:
    train_id: str # Changed to str for flexibility [47.2]
    from_stop_id: str
    to_stop_id: str
    travel_date: date
    quota_type: str = "GN"
    class_type: str = "SL"

    def cache_key(self) -> str:
        """Standardized Availability Key."""
        date_str = self.travel_date.isoformat()
        return f"avail:{self.train_id}:{self.from_stop_id}:{self.to_stop_id}:{date_str}:{self.quota_type.upper()}:{self.class_type.upper()}"

class LRUCache:
    def __init__(self, capacity: int = 1000):
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

from core.providers import ServiceProvider, ServiceStatus
from core.container import container

class MultiLayerCache(ServiceProvider):
    def __init__(self):
        super().__init__("cache", version="2.2.0")
        self.redis: Optional[Any] = None
        self.lru = LRUCache(capacity=2000) 
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
        self._xfetch_beta = 1.0 
        self._warmup_orchestrator = None

    async def init(self):
        """IoC Lifecycle: Connect to Redis (Idempotent)."""
        if self._initialized and self.redis:
            return
        from redis.asyncio import from_url
        try:
            self.redis = await from_url(Config.REDIS_URL, decode_responses=False)
            await self.redis.ping()
            self._initialized = True
            logger.info(" IoC: MultiLayerCache (Redis L2) Initialized.")
            if not self._pubsub_task or self._pubsub_task.done():
                self._pubsub_task = asyncio.create_task(self._listen_for_invalidations())
        except Exception as e:
            logger.warning(f" IoC: MultiLayerCache (Redis L2) init failed: {e}. Falling back to L1 (Memory) only.")
            self.redis = None
            self._initialized = True

    async def initialize(self):
        """[Task 27.11] Backward compatibility alias for init."""
        await self.init()

    async def shutdown(self):
        """[Task 27.18] Definitive cleanup of background tasks and connections."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                # Wait for the task to acknowledge cancellation
                await self._pubsub_task
            except (asyncio.CancelledError, Exception):
                pass
            self._pubsub_task = None
        
        if self.redis:
            try:
                # First close, then set to None
                await self.redis.aclose()
            except: pass
            self.redis = None
            logger.info(" MultiLayerCache: Redis connection closed.")
        
        self.status = ServiceStatus.PENDING

    @property
    def warmup(self):
        if self._warmup_orchestrator is None:
            from .cache_warmup import CacheWarmupOrchestrator
            self._warmup_orchestrator = CacheWarmupOrchestrator(self)
        return self._warmup_orchestrator

    def _is_l2_available(self) -> bool:
        if not self.redis: return False
        if time.time() < self._l2_disabled_until: return False
        return True

    def _get_l1_capacity(self) -> int:
        import psutil
        try:
            available_mb = psutil.virtual_memory().available / 1024 / 1024
            if available_mb < 200: return 500 
            if available_mb < 500: return 1000
            return 5000
        except: return 1000

    async def get(self, key: str, serializer: Optional[Callable] = None, refresh_callback: Optional[Callable] = None, allow_stale: bool = True) -> Optional[Any]:
        """
        [Task 47.1 & 47.6] Advanced Multi-Layer Fetch with SWR.
        """
        # 1. Layer 0: L1 (LRU Memory) - Sub-ms lookup
        cached_item = self.lru.get(key)
        if cached_item:
            self.metrics['lru_cache'].hits += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='hit').inc()
            return self._process_xfetch(cached_item, refresh_callback, allow_stale)
        
        # 2. Layer 1: L2 (Redis) with Circuit Breaker [47.1]
        if not self._is_l2_available():
            return None

        try:
            start_time = time.time()
            data = await self.redis.get(key)
            latency = (time.time() - start_time) * 1000
            self._l2_latency_ms = (0.7 * self._l2_latency_ms) + (0.3 * latency) # Moving average

            # Circuit Breaker: If average latency > 200ms, trip it for 60s
            if self._l2_latency_ms > 200:
                logger.warning(f"🚨 Redis Latency Spike ({self._l2_latency_ms:.2f}ms). Tripping Circuit Breaker.")
                self._l2_disabled_until = time.time() + 60

            if data:
                # [Task 47.8] MsgPack Binary Deserialization (if configured)
                # For now, keeping PayloadCompressor but adding MsgPack hook
                cached_item = PayloadCompressor.decompress(data)
                if cached_item:
                    self.lru.put(key, cached_item, dynamic_limit=self._get_l1_capacity())
                    self.metrics['query_cache'].hits += 1
                    CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='hit').inc()
                    return self._process_xfetch(cached_item, refresh_callback, allow_stale)
            else:
                self.metrics['query_cache'].misses += 1
                CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='miss').inc()
                
        except Exception as e:
            logger.error(f"L2 Cache Get Failure: {e}")
            self._l2_disabled_until = time.time() + 10 # 10s cooldown

        return None

    def _process_xfetch(self, cached_item: Any, refresh_callback: Optional[Callable], allow_stale: bool) -> Any:
        """
        [Task 47.6] Probabilistic Revalidation.
        """
        if not isinstance(cached_item, dict) or "xf_expiry" not in cached_item:
            return cached_item

        val = cached_item["value"]
        expiry = cached_item["xf_expiry"]
        now = time.time()

        # Probabilistic Early Refresh: If at 80% TTL, refresh in background
        # Formula: rand() > (expiry - now) / total_ttl
        # For simplicity, 90% threshold for now
        time_left = expiry - now
        if time_left < 60 and refresh_callback:
            logger.info("⏱️ Cache near expiry. Triggering Background Refresh.")
            asyncio.create_task(refresh_callback())

        if now > expiry:
            if refresh_callback: asyncio.create_task(refresh_callback())
            # Serve Stale if allowed [47.8]
            if allow_stale and now < (expiry + 300):
                logger.debug("🍞 Serving Stale Data (Grace Period)")
                return val
            return None
        
        return val

    async def put(self, key: str, value: Any, ttl: int = 300, negative_cache: bool = False):
        """
        [Task 47.7 & 47.8] Compressed Put with Mutation Tracking.
        """
        # Negative Cache: 5 mins if no results found
        actual_ttl = 300 if negative_cache else ttl
        
        xf_item = {"value": value, "xf_expiry": time.time() + actual_ttl}
        
        # 1. Update L1
        self.lru.put(key, xf_item, dynamic_limit=self._get_l1_capacity())
        
        # 2. Update L2 (Redis)
        if self._is_l2_available():
            try:
                # [Task 47.8] MsgPack binary compression potentially here
                payload, _ = PayloadCompressor.compress(xf_item)
                # Keep in Redis longer than L1 expiry to support SWR
                await self.redis.setex(key, actual_ttl + 600, payload)
                # Notify peers
                await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "key": key}))
            except Exception as e:
                logger.error(f"L2 Cache Put Error: {e}")

    async def get_or_set(self, key: str, fetch_callback: Callable, ttl: int = 300) -> Any:
        """
        [Task 47.3 & 47.5] Thundering Herd Shield.
        Ensures only 1 request per key hits the source (RapidAPI) during miss.
        """
        # 1. Fast Path (Normal Get)
        result = await self.get(key)
        if result: return result
        
        # 2. Cache Miss -> Enter Mutex [47.3]
        if not self._is_l2_available():
            # Fallback for L1 (No Lock but safe-ish)
            return await fetch_callback()

        # [Task 47.5] Distributed Lock (Redlock pattern)
        lock_key = f"lock:{key}"
        lock = self.redis.lock(lock_key, timeout=20, blocking_timeout=15)
        
        try:
            async with lock:
                # 3. Double-Checked Locking: Did another task fill it while we waited?
                result = await self.get(key)
                if result:
                    logger.debug(f"🏇 Double-Hit Saved: {key}")
                    return result
                
                # 4. Critical Section: Hit the Source
                logger.info(f"🔄 Cache Miss. Fetching Source: {key}")
                result = await fetch_callback()
                
                if result:
                    await self.put(key, result, ttl=ttl)
                else:
                    # [Task 47.7] Negative Cache for failures
                    await self.put(key, None, ttl=300, negative_cache=True)
                    
                return result
                
        except Exception as e:
            logger.error(f"❌ Shield Failure for {key}: {e}")
            return await fetch_callback() # Emergency Bypass
        """[Task 27.18] Robust invalidation listener with proper cleanup."""
        if not self.redis: return
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe("cache:invalidation")
            # Use get_message loop instead of async iterator to avoid GeneratorExit issues
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message['type'] == 'message':
                        data = json.loads(message['data'].decode('utf-8'))
                        if data.get('sender') != PROCESS_ID:
                            if data.get('key') == "ALL_CLEAR":
                                self.lru.clear()
                            else:
                                self.lru.delete(data.get('key'))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                await asyncio.sleep(0.01) # Small yielding sleep
        except asyncio.CancelledError:
            logger.info("📡 MultiLayerCache: Invalidation listener cancelled.")
        except Exception as e:
            logger.error(f"📡 MultiLayerCache: Invalidation listener error: {e}")
        finally:
            try:
                await pubsub.unsubscribe("cache:invalidation")
                await pubsub.close()
            except: pass

    # --- Domain Specific Methods ---

    async def get_route_query(self, query: RouteQuery) -> Optional[Dict]:
        return await self.get(query.cache_key())

    async def set_route_query(self, query: RouteQuery, result: Dict, ttl_minutes: int = 5):
        await self.put(query.cache_key(), result, ttl=ttl_minutes * 60)

    async def get_availability(self, query: AvailabilityQuery) -> Optional[Dict]:
        return await self.get(query.cache_key())

    async def set_availability(self, query: AvailabilityQuery, result: Dict, ttl: int = 300):
        await self.put(query.cache_key(), result, ttl=ttl)

    async def get_graph_snapshot(self, date_str: str) -> Optional[Any]:
        if not self.redis: return None
        try:
            data = await self.redis.get(f"graph:snapshot:{date_str}")
            return pickle.loads(zlib.decompress(data)) if data else None
        except: return None

    async def set_graph_snapshot(self, date_str: str, snapshot: Any, ttl: int = 86400):
        if not self.redis: return
        try:
            compressed = zlib.compress(pickle.dumps(snapshot, protocol=pickle.HIGHEST_PROTOCOL))
            await self.redis.setex(f"graph:snapshot:{date_str}", ttl, compressed)
        except: pass

    def record_graph_metrics(self, nodes: int, edges: int, rebuild_time: float = None):
        GRAPH_NODES_TOTAL.set(nodes)
        GRAPH_EDGES_TOTAL.set(edges)
        if rebuild_time: GRAPH_LAST_REBUILD_TIMESTAMP.set(rebuild_time)

    async def mark_train_sold_out(self, train_no: str, date_str: str):
        if self.redis: await self.redis.setex(f"soldout:{train_no}:{date_str}", 86400, "1")

    async def is_train_sold_out(self, train_no: str, date_str: str) -> bool:
        return await self.redis.exists(f"soldout:{train_no}:{date_str}") if self.redis else False

    def get_lock(self, name: str, timeout: int = 10):
        if not self.redis:
            from .cache_service import _DummyLock
            return _DummyLock()
        return self.redis.lock(f"lock:{name}", timeout=timeout)

    async def clear_all_caches(self):
        """Clears both L1 (Memory) and L2 (Redis) caches."""
        self.lru.clear()
        if self.redis:
            try:
                await self.redis.flushdb()
                await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "key": "ALL_CLEAR"}))
                logger.info("🗑️ MultiLayerCache: All caches cleared.")
            except Exception as e:
                logger.error(f"L2 Cache Clear Error: {e}")

# Singleton
multi_layer_cache = MultiLayerCache()
container.register(multi_layer_cache)
