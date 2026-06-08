CACHE_VERSION = "v1"

"""
Multi-Layer Cache System - IRCTC-Level Performance
Upgraded with Pub/Sub Invalidation and Memory Policies (TODO #26).
"""

import asyncio

# chaos_trap was in archived core/nexus — stub it out
def chaos_trap(fn):
    return fn

import json
import logging
import uuid
import time
import math
import random
import hashlib
import zlib
import functools
import msgpack
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
        return f"route:p:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"

@dataclass
class DiscoveryQuery:
    """[Echo Cache] Global Discovery Key for (Src, Dst, Date) regardless of Persona."""
    source: str
    destination: str
    travel_date: date
    
    def cache_key(self) -> str:
        s = self.source.strip().upper()
        d = self.destination.strip().upper()
        dt = self.travel_date.isoformat()
        return f"discovery:raw:{s}:{d}:{dt}"

@dataclass
class AvailabilityQuery:
    train_id: Union[str, int] # Accept numeric or string IDs
    from_stop_id: Union[str, int]
    to_stop_id: Union[str, int]
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

from core.integration.providers import ServiceProvider, ServiceStatus
from core.infrastructure.container import container

class MultiLayerCache(ServiceProvider):
    # Raw (uncompressed, direct) cache access for session_lock_service compatibility
    async def get_raw(self, key: str) -> Any:
        if self.redis:
            try:
                return await self.redis.get(key)
            except Exception as e:
                logger.error(f"get_raw error: {e}")
                return None
        return self.lru.get(key)

    async def set_raw(self, key: str, value: Any, ttl: int = 600):
        if self.redis:
            try:
                await self.redis.setex(key, ttl, value)
            except Exception as e:
                logger.error(f"set_raw error: {e}")
        else:
            self.lru.put(key, value)

    async def delete_raw(self, key: str):
        if self.redis:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.error(f"delete_raw error: {e}")
        self.lru.delete(key)
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
        self._xfetch_beta = 1.0 
        self._warmup_orchestrator = None
        self._init_lock = asyncio.Lock()
        self.health_latch = True # [Task 5.3] Zero-latency Latch
        self._heartbeat_task = None
        # [Task 22] Unified Resilience
        from core.resilience.core import CircuitBreaker, CircuitConfig
        self.redis_circuit = CircuitBreaker("redis_l2", CircuitConfig(failure_threshold=3, timeout_seconds=60.0))

    async def init(self):
        """IoC Lifecycle: Connect to Redis (Idempotent)."""
        if self._initialized:
            logger.debug(f" [CACHE:INIT] '{self.name}' already initialized.")
            return
        
        from core.infrastructure.redis_manager import URL, OPTS
        from redis.asyncio import from_url
        
        # [Phase 3] Diagnostic Instrumentation: Connect Start
        logger.info(f"⚡ [REDIS:CONNECT] Initializing L2 link to {URL[:20]}...")
        start_time = time.perf_counter()
        
        try:
            # [Phase 1/Task 127] Ensure the entire connection block has a strict timeout
            async with asyncio.timeout(7.0):
                # Step 1: Handshake (Socket/TLS)
                # [Nexus Fix] Use decode_responses=False for binary payloads (pickle/zlib)
                CACHE_OPTS = OPTS.copy()
                CACHE_OPTS["decode_responses"] = False
                self.redis = from_url(URL, **CACHE_OPTS)
                handshake_time = (time.perf_counter() - start_time) * 1000
                logger.info(f"🤝 [REDIS:HANDSHAKE] TLS/TCP Handshake complete in {handshake_time:.2f}ms")
                
                # Step 2: Protocol Ping
                ping_start = time.perf_counter()
                await self.redis.ping()
                ping_latency = (time.perf_counter() - ping_start) * 1000
                logger.info(f"🏓 [REDIS:PING] Protocol verify successful. Latency: {ping_latency:.2f}ms")
                
                self._initialized = True
                self.health_latch = True
                self.status = ServiceStatus.HEALTHY
                
                if not self._pubsub_task or self._pubsub_task.done():
                    self._pubsub_task = asyncio.create_task(self._listen_for_invalidations())
                
                if not self._heartbeat_task or self._heartbeat_task.done():
                    # [Phase 4] Nexus Heartbeat Decoupling: Moved to background task
                    self._heartbeat_task = asyncio.create_task(self._run_heartbeat())
                
                self._eviction_task = asyncio.create_task(self._run_eviction_sentinel())
                
        except (asyncio.TimeoutError, Exception) as e:
            error_type = "Timeout" if isinstance(e, asyncio.TimeoutError) else type(e).__name__
            total_time = (time.perf_counter() - start_time) * 1000
            logger.warning(f"❌ [REDIS:FAILED] L2 Init dropped after {total_time:.2f}ms ({error_type}): {e}. Falling back to L1 (Memory).")
            self.redis = None
            self._initialized = True
            self.health_latch = False
            self.status = ServiceStatus.DEGRADED # Signal we are in fallback mode

    async def _run_heartbeat(self):
        """[Task 5.3] Periodic Redis Health Check to update the Latch."""
        while True:
            # [Task 21] Heartbeat
            from core.nexus.bootstrapper import nexus_boot
            from core.nexus.watchdog import nexus_watchdog
            nexus_boot.recovery.record_heartbeat("cache")
            nexus_watchdog.poke("redis_heartbeat")
            
            await asyncio.sleep(15)
            if self.redis:
                try:
                    await self.redis.ping()
                    if not self.health_latch:
                         # [Task 26.4] L2 Recovery Pulse: Re-Sync Regional L1s
                         logger.info("📡 [NEXUS:CACHE] L2 RECOVERY PULSE. Flushing regional L1 for fresh sync.")
                         await self.redis.publish("cache:invalidation", json.dumps({"sender": PROCESS_ID, "key": "ALL_CLEAR"}))
                    self.health_latch = True
                except:
                    self.health_latch = False
                    logger.error("[NEXUS:CACHE] Redis Heartbeat Lost.")

    async def _run_eviction_sentinel(self):
        """[Task 5.5] Periodically clear stale search results (> 1 hour)."""
        while True:
            await asyncio.sleep(600) # Every 10 mins
            logger.info("[NEXUS:CACHE] Eviction Sentinel: Scanning for stale L1 fragments...")
            # L1 (LRU) manages itself by capacity, but we can clear specific old domains
            # This is a placeholder for deep eviction logic
            pass

    async def initialize(self):
        """[Task 27.11] Backward compatibility alias for init."""
        await self.init()

    async def connect(self):
        """Alias for init to match lifespan connect calls."""
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
            from .cache_warmup import CacheWarmupOrchestrator  # type: ignore
            self._warmup_orchestrator = CacheWarmupOrchestrator(self)
        return self._warmup_orchestrator

    def _is_l2_available(self) -> bool:
        from core.resilience.core import CircuitState
        if not self.redis: return False
        
        # [Task 26.1] Chaos Severance Check
        from core.nexus.audit.chaos import nexus_chaos
        if nexus_chaos.is_severed("cache_l2"):
             return False

        if self.redis_circuit.state == CircuitState.OPEN: return False
        return True

    def _get_l1_capacity(self) -> int:
        import psutil
        try:
            available_mb = psutil.virtual_memory().available / 1024 / 1024
            if available_mb < 200: return 500 
            if available_mb < 500: return 1000
            return 5000
        except: return 1000

    @chaos_trap("cache_l2")
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
        if not self._is_l2_available() or self.redis is None:
            return None

        try:
            async def _fetch():
                start_time = time.time()
                data = await self.redis.get(key) if self.redis else None
                latency = (time.time() - start_time) * 1000
                if latency > 200:
                     raise TimeoutError(f"Redis high latency: {latency:.1f}ms")
                return data

            data = await self.redis_circuit.execute(_fetch)

            if data:
                # Determine if it's pickle or JSON based on signature or domain
                # Rule: discovery:raw:* is always pickle for Route objects
                # [Task 145] Multi-Modal Decoding
                if key.startswith("hot_path:"):
                    # Fast binary path for Elite routes
                    cached_item = msgpack.unpackb(data, raw=False)
                elif key.startswith("discovery:raw:") or key.startswith("nexus:search:"):
                    # Deep discovery and search results
                    cached_item = PayloadCompressor.decompress(data)
                else:
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
            logger.error(f"L2 Cache Get Failure/Circuit Trip: {e}")

        return None

    def _get_get_l1_capacity(self) -> int:
        return self._get_l1_capacity()

    def _process_xfetch(self, cached_item: Any, refresh_callback: Optional[Callable], allow_stale: bool) -> Any:
        """
        [High-End] X-Fetch Algorithm (Probabilistic Early Refresh).
        Formula: now - (delta * beta * log(random())) > expiry
        Prevents cache-miss spikes for high-traffic results.
        """
        if not isinstance(cached_item, dict) or "xf_expiry" not in cached_item:
            return cached_item

        val = cached_item["value"]
        expiry = cached_item["xf_expiry"]
        delta = cached_item.get("xf_delta", 0.1) # Time taken to compute
        now = time.time()

        # Step 1: Probabilistic Revalidation (Vlachos et al.)
        # If the result was expensive to compute (high delta), we refresh it earlier
        import math, random
        beta = self._xfetch_beta
        # Use a safe log to avoid domain errors
        p_val = now - (delta * beta * math.log(random.random() or 0.0001))
        
        if p_val > expiry and refresh_callback:
            # We hit the probabilistic window! Refresh in background.
            logger.info(f"🔄 [ECHO:X-FETCH] Probabilistic Refresh triggered (Delta: {delta:.2f}s, Rem: {expiry-now:.1f}s)")
            asyncio.create_task(refresh_callback())
        
        # Step 2: Absolute Expiry Check
        if now > expiry:
            if refresh_callback: asyncio.create_task(refresh_callback())
            
            # [Task 26.3] Ghost Shadowing Mode
            # If Redis is DOWN, we extend the grace period to 1 HOUR (Planet-Scale survivability)
            grace_period = 3600 if not self._is_l2_available() else 300
            
            if allow_stale and now < (expiry + grace_period):
                logger.debug(f"👻 [NEXUS:GHOST] Serving Ghost Data (Outage Grace: {grace_period}s)")
                return val
            return None
        
        return val

    async def get_or_set(self, key: str, fetch_callback: Callable, ttl: int = 300, use_pickle: bool = False) -> Any:
        """
        [Task 47.3 & 47.5] Thundering Herd Shield.
        Ensures only 1 request per key hits the source (RapidAPI) during miss.
        """
        # 1. Fast Path (Normal Get)
        # Use simple get for standard JSON, but for Discovery we might want Pickle
        result = await self.get(key)
        if result: return result
        
        # 2. Cache Miss -> Enter Mutex [47.3]
        if not self._is_l2_available():
            # Fallback for L1 (No Lock but safe-ish)
            return await fetch_callback()

        # [Task 47.5] Distributed Lock (Redlock pattern)
        lock_key = f"lock:{key}"
        if self.redis is None:
            return await fetch_callback()
        
        lock = self.redis.lock(lock_key, timeout=20, blocking_timeout=15)
        
        try:
            async with lock:
                # 3. Double-Checked Locking: Did another task fill it while we waited?
                result = await self.get(key)
                if result:
                    logger.debug(f"Double-Hit Saved: {key}")
                    return result
                
                # 4. Critical Section: Hit the Source
                logger.info(f"Cache Miss. Fetching Source: {key}")
                start_fetch = time.time()
                result = await fetch_callback()
                fetch_delta = time.time() - start_fetch
                
                if result:
                    await self.put(key, result, ttl=ttl, use_pickle=use_pickle, delta=fetch_delta)
                else:
                    # [Task 47.7] Negative Cache for failures
                    await self.put(key, None, ttl=300, negative_cache=True)
                    
                return result
                
        except Exception as e:
            logger.error(f"Shield Failure for {key}: {e}")
            return await fetch_callback() # Emergency Bypass

    async def put(self, key: str, value: Any, ttl: int = 300, negative_cache: bool = False, use_pickle: bool = False, use_msgpack: bool = False, delta: float = 0.1):
        """
        [Task 47.7 & 47.8] Compressed Put with Mutation Tracking.
        """
        # [Task 26.2] Anti-Stampede TTL Staggering (Jittered Expiry)
        from random import uniform
        jitter_factor = uniform(0.85, 1.0)
        actual_ttl = int((300 if negative_cache else ttl) * jitter_factor)
        
        xf_item = {
            "value": value, 
            "xf_expiry": time.time() + actual_ttl,
            "xf_delta": delta # Store compute cost
        }
        
        # 1. Update L1
        self.lru.put(key, xf_item, dynamic_limit=self._get_l1_capacity())
        
        # 2. Update L2 (Redis)
        if self._is_l2_available() and self.redis is not None:
            try:
                if use_msgpack:
                    # [Task 145] Binary-First msgpack Path
                    # Convert to dict if it has model_dump or dict method, handle datetimes
                    payload = msgpack.packb(xf_item, default=lambda x: x.isoformat() if isinstance(x, (datetime, date)) else (x.model_dump() if hasattr(x, 'model_dump') else (x.dict() if hasattr(x, 'dict') else str(x))), use_bin_type=True)
                elif use_pickle:
                    # Fallback: using PayloadCompressor (JSON) instead of insecure pickle
                    payload, _ = PayloadCompressor.compress(xf_item)
                else:
                    payload, _ = PayloadCompressor.compress(xf_item)
                    
                await self.redis.setex(key, actual_ttl + 600, payload)
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
                        m_data = message['data']
                        if isinstance(m_data, bytes):
                            m_data = m_data.decode('utf-8')
                        data = json.loads(m_data)
                        if data.get('sender') != PROCESS_ID:
                            key = data.get('key')
                            if key == "ALL_CLEAR":
                                self.lru.clear()
                            elif key:
                                # [Nexus] Hash Invalidation Support
                                # If the key is a hash discovery field, we ignore for now as it's incremental
                                # But we clear L1 discovery candidates if any
                                self.lru.delete(key)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
                await asyncio.sleep(0.01) # Small yielding sleep
        except asyncio.CancelledError:
            logger.info("MultiLayerCache: Invalidation listener cancelled.")
        except Exception as e:
            logger.error(f"MultiLayerCache: Invalidation listener error: {e}")
        finally:
            try:
                await pubsub.unsubscribe("cache:invalidation")
                await pubsub.close()
            except: pass

    # --- Hash-based Discovery Methods (Streaming) ---

    async def hset_routes(self, key: str, routes: List[Any], ttl: int = 3600):
        """[Nexus Stream] Incrementally add routes to a discovery hash."""
        if not self.redis: return
        try:
            mapping = {}
            for r in routes:
                jid = getattr(r, 'journey_id', str(uuid.uuid4())[:8])
                # We use PayloadCompressor (JSON/zlib) instead of pickle
                r_dict = r.model_dump() if hasattr(r, 'model_dump') else (r.dict() if hasattr(r, 'dict') else r)
                compressed, _ = PayloadCompressor.compress(r_dict)
                mapping[jid] = compressed
            
            if mapping:
                await self.redis.hset(key, mapping=mapping)
                await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache hset_routes Error: {e}")

    async def hget_routes(self, key: str) -> List[Any]:
        """[Nexus Stream] Retrieve all gathered routes from a discovery hash."""
        if not self.redis: return []
        try:
            all_fields = await self.redis.hgetall(key)
            results = []
            for jid, data in all_fields.items():
                s_jid = jid
                if isinstance(jid, bytes):
                    s_jid = jid.decode('utf-8')
                if s_jid.startswith('_'): continue
                try:
                    results.append(PayloadCompressor.decompress(data))
                except: pass
            return results
        except Exception as e:
            logger.error(f"Cache hget_routes Error: {e}")
            return []

    async def hset_status(self, key: str, status: str):
        """Mark discovery as 'partial' or 'complete'."""
        if self.redis:
             await self.redis.hset(key, "_status", status)

    async def hget_status(self, key: str) -> str:
        if not self.redis: return "miss"
        val = await self.redis.hget(key, "_status")
        if isinstance(val, bytes):
            return val.decode('utf-8')
        return val if val else "miss"

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
        # Snapshot loading from Redis is disabled to prevent massive memory usage and RCE.
        return None

    async def set_graph_snapshot(self, date_str: str, snapshot: Any, ttl: int = 86400):
        # Snapshot caching to Redis is disabled.
        pass

    def record_graph_metrics(self, nodes: int, edges: int, rebuild_time: Optional[float] = None):
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
                logger.info("MultiLayerCache: All caches cleared.")
            except Exception as e:
                logger.error(f"L2 Cache Clear Error: {e}")

# Singleton
multi_layer_cache = MultiLayerCache()
container.register(multi_layer_cache)
