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

import redis.asyncio as redis

from database.config import Config
from database.session import SessionLocal

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
        self.redis: Optional[redis.Redis] = None
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
            self.redis = redis.Redis.from_url(redis_url, decode_responses=False, ssl_cert_reqs=None)
            await self.redis.ping()
            
            # Suggestion #26: Memory Policies
            try:
                await self.redis.config_set("maxmemory-policy", "allkeys-lru")
            except: pass

            # Start Pub/Sub Listener (Task 25)
            self._pubsub_task = asyncio.create_task(self._listen_for_invalidations())
            
            logger.info(f"Multi-layer cache initialized (Instance: {PROCESS_ID})")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            self.redis = None
        self._initialized = True

    # Suggestion #23: Bloom Filter for Sold Out Trains
    async def mark_train_sold_out(self, train_no: str, date_str: str):
        if not self.redis: return
        key = f"soldout:{train_no}:{date_str}"
        await self.redis.setex(key, 3600 * 24, "1") # 24h cache

    async def is_train_sold_out(self, train_no: str, date_str: str) -> bool:
        if not self.redis: return False
        return await self.redis.exists(f"soldout:{train_no}:{date_str}")

    async def _listen_for_invalidations(self):
        """Background task to clear local LRU on Pub/Sub signal (Task 25)."""
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
        # Layer 0
        lru_data = self.lru.get(key)
        if lru_data:
            self.metrics['lru_cache'].hits += 1
            return lru_data
        
        if not self.redis: return None
        
        # Layer 1
        data = await self.redis.get(key)
        if data:
            res = json.loads(data.decode('utf-8'))
            self.lru.put(key, res)
            self.metrics['query_cache'].hits += 1
            return res
        self.metrics['query_cache'].misses += 1
        return None

    async def set_route_query(self, query: RouteQuery, result: Dict, ttl_minutes: int = 5):
        key = query.cache_key()
        self.lru.put(key, result)
        if self.redis:
            await self.redis.setex(key, ttl_minutes * 60, json.dumps(result, default=str))
            self.metrics['query_cache'].sets += 1
            # Broadcast invalidation to others (Task 25)
            await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "type": "set", "key": key}))

    async def get_availability(self, query: AvailabilityQuery) -> Optional[Dict]:
        key = query.cache_key()
        # Layer 0
        lru_data = self.lru.get(key)
        if lru_data:
            self.metrics['lru_cache'].hits += 1
            return lru_data
        
        if not self.redis: return None
        
        # Layer 1
        data = await self.redis.get(key)
        if data:
            res = json.loads(data.decode('utf-8'))
            self.lru.put(key, res)
            self.metrics['query_cache'].hits += 1
            return res
        self.metrics['query_cache'].misses += 1
        return None

    async def set_availability(self, query: AvailabilityQuery, result: Dict, ttl: int = 300):
        key = query.cache_key()
        self.lru.put(key, result)
        if self.redis:
            await self.redis.setex(key, ttl, json.dumps(result, default=str))
            self.metrics['query_cache'].sets += 1

    async def get_cache_stats(self) -> Dict:
        return {k: v.to_dict() for k, v in self.metrics.items()}

    # --- Task 19: Snapshot Redis Storage ---
    async def get_graph_snapshot(self, date_str: str) -> Optional[Any]:
        """Fetch compressed graph snapshot from Redis."""
        if not self.redis: return None
        key = f"graph:snapshot:{date_str}"
        try:
            data = await self.redis.get(key)
            if data:
                # Decompress and Unpickle
                decompressed = zlib.decompress(data)
                return pickle.loads(decompressed)
        except Exception as e:
            logger.error(f"Failed to load snapshot from Redis: {e}")
        return None

    async def set_graph_snapshot(self, date_str: str, snapshot: Any, ttl: int = 86400):
        """Save compressed graph snapshot to Redis (24h TTL)."""
        if not self.redis: return
        key = f"graph:snapshot:{date_str}"
        try:
            # Pickle -> Compress -> Save
            serialized = pickle.dumps(snapshot, protocol=pickle.HIGHEST_PROTOCOL)
            compressed = zlib.compress(serialized)
            await self.redis.setex(key, ttl, compressed)
            logger.info(f"✅ Saved {len(compressed)/1024/1024:.2f}MB snapshot to Redis for {date_str}")
        except Exception as e:
            logger.error(f"Failed to save snapshot to Redis: {e}")

    # --- Lock Support (from CacheService migration) ---
    def get_lock(self, name: str, timeout: int = 10):
        """Get a distributed Redis lock."""
        if self.redis:
            return self.redis.lock(name, timeout=timeout)
        return None

    # --- Sync Wrappers (for SOS legacy support) ---
    def set_sync(self, key: str, value: Any, ttl: int = 3600):
        """Synchronous set for non-async parts of the code."""
        if self.redis:
            import redis
            # We need a sync connection for this
            sync_redis = redis.from_url(Config.REDIS_URL)
            sync_redis.setex(key, ttl, json.dumps(value))

multi_layer_cache = MultiLayerCache()
