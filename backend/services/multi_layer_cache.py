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
            logger.info("📡 IoC: MultiLayerCache (Redis L2) Initialized.")
            if not self._pubsub_task or self._pubsub_task.done():
                self._pubsub_task = asyncio.create_task(self._listen_for_invalidations())
        except Exception as e:
            logger.error(f"IoC: Redis init failed: {e}")
            raise e

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
            logger.info("🛑 MultiLayerCache: Redis connection closed.")
        
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

    async def get(self, key: str, serializer: Optional[Callable] = None, refresh_callback: Optional[Callable] = None) -> Optional[Any]:
        # Layer 0: L1 (LRU)
        cached_item = self.lru.get(key)
        if cached_item:
            self.metrics['lru_cache'].hits += 1
            CACHE_OPERATIONS_TOTAL.labels(layer='L1_MEM', operation='get', result='hit').inc()
        
        # Layer 1: L2 (Redis)
        if not cached_item and self._is_l2_available():
            try:
                data = await self.redis.get(key)
                if data:
                    cached_item = PayloadCompressor.decompress(data)
                    if cached_item:
                        self.lru.put(key, cached_item, dynamic_limit=self._get_l1_capacity())
                        self.metrics['query_cache'].hits += 1
                        CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='hit').inc()
                else:
                    self.metrics['query_cache'].misses += 1
                    CACHE_OPERATIONS_TOTAL.labels(layer='L2_REDIS', operation='get', result='miss').inc()
            except Exception as e:
                logger.error(f"L2 Cache Get Error: {e}")

        if not cached_item: return None

        # SWR / XFetch Logic
        if isinstance(cached_item, dict) and "xf_expiry" in cached_item:
            val = cached_item["value"]
            expiry = cached_item["xf_expiry"]
            if time.time() > expiry:
                if refresh_callback: asyncio.create_task(refresh_callback())
                if time.time() < (expiry + 600): return val # Grace period
                return None
            return serializer(val) if serializer else val

        return cached_item

    async def put(self, key: str, value: Any, ttl: int = 300):
        xf_item = {"value": value, "xf_expiry": time.time() + ttl}
        self.lru.put(key, xf_item, dynamic_limit=self._get_l1_capacity())
        if self._is_l2_available():
            try:
                payload, _ = PayloadCompressor.compress(xf_item)
                await self.redis.setex(key, ttl + 3600, payload)
                await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "key": key}))
            except Exception as e:
                logger.error(f"L2 Cache Put Error: {e}")

    async def _listen_for_invalidations(self):
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

# Singleton
multi_layer_cache = MultiLayerCache()
container.register(multi_layer_cache)
