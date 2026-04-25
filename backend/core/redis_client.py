import os
import sys
from pathlib import Path
import logging
import asyncio
import time
from typing import AsyncGenerator, Optional, Any, Dict, Union, Awaitable
from contextlib import asynccontextmanager
import inspect
import redis
import redis.asyncio as aioredis
from redis.exceptions import AuthenticationError, ConnectionError, TimeoutError
from database.config import Config

logger = logging.getLogger("nexus.redis")

def sanitize_redis_url(url: str) -> str:
    """
    Ensures SSL/TLS and Auth compatibility for Cloud Providers (Upstash/RedisCloud).
    Corrects common misconfigurations where password is provided without username.
    """
    if not url: return "redis://localhost:6379/0"
    
    from urllib.parse import urlparse, urlunparse
    
    is_cloud = "upstash.io" in url or "rediscloud.com" in url
    if is_cloud and url.startswith("redis://"):
        logger.info("[REDIS:BOOT] Detected Cloud Redis. Upgrading to SSL (rediss://)")
        url = url.replace("redis://", "rediss://", 1)
    
    parsed = urlparse(url)
    new_url = url
    if is_cloud and not parsed.username and parsed.password:
        new_url = url.replace("://:", "://default:", 1)
    elif is_cloud and parsed.username and not parsed.password:
        scheme = parsed.scheme or "rediss"
        netloc = f"default:{parsed.username}@{parsed.hostname}"
        if parsed.port: netloc += f":{parsed.port}"
        new_url = urlunparse((scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    final_parsed = urlparse(new_url)
    masked = f"{final_parsed.scheme}://{final_parsed.username or '***'}:***@{final_parsed.hostname}:{final_parsed.port or 6379}{final_parsed.path}"
    logger.info(f"[REDIS:URL_VERIFY] Verified connection string: {masked}")
    
    return new_url

URL = sanitize_redis_url(Config.REDIS_URL)

OPTS = {
    "decode_responses": True,
    "ssl_cert_reqs": "none",
    "socket_timeout": 5.0,
    "socket_connect_timeout": 5.0,
    "retry_on_timeout": True,
    "max_connections": 100,
    "health_check_interval": 30
}

class ResilientAsyncRedis:
    """
    [Phase 1: Day 1] Titan-Grade Redis Wrapper.
    Handles AuthenticationError, Circuit Breaking, and L1 Fallback.
    """
    def __init__(self, url: str, options: dict):
        self.url = url
        self.options = options
        self._client: Optional[aioredis.Redis] = None
        self._lock = asyncio.Lock()
        self.consecutive_failures = 0
        self.circuit_open = False
        self.last_failure_time = 0.0

    async def get_client(self) -> aioredis.Redis:
        async with self._lock:
            if self._client is None:
                logger.info("[REDIS:RECOVERY] Re-initializing connection pool...")
                self._client = aioredis.from_url(self.url, **self.options)
            return self._client

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _handle_error(self, e: Exception):
        self.consecutive_failures += 1
        if isinstance(e, (AuthenticationError, ConnectionError)):
            logger.error(f"🚨 [REDIS:CRITICAL] {type(e).__name__}: {e}")
            self._client = None # Force re-init on next call
            if self.consecutive_failures > 3:
                self.circuit_open = True
                self.last_failure_time = time.time()
        else:
            logger.warning(f"⚠️ [REDIS:TRANSIENT] {e}")

    async def get(self, key: str) -> Optional[Any]:
        if self.circuit_open:
            if time.time() - self.last_failure_time > 60:
                self.circuit_open = False
                self.consecutive_failures = 0
            else:
                return None # Circuit is open

        try:
            client = await self.get_client()
            val = await self._maybe_await(client.get(key))
            self.consecutive_failures = 0
            return val
        except Exception as e:
            await self._handle_error(e)
            return None

    async def setex(self, key: str, ttl: int, value: Any):
        try:
            client = await self.get_client()
            await self._maybe_await(client.setex(key, ttl, value))
            self.consecutive_failures = 0
        except Exception as e:
            await self._handle_error(e)

    async def ping(self) -> bool:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.ping())
        except Exception:
            return False

    async def publish(self, channel: str, message: str):
        try:
            client = await self.get_client()
            await self._maybe_await(client.publish(channel, message))
        except Exception as e:
            await self._handle_error(e)

    def pubsub(self):
        if self._client:
            return self._client.pubsub()
        return None

    async def incr(self, key: str) -> int:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.incr(key))
        except Exception as e:
            await self._handle_error(e)
            return 1 # Fallback to 1 to allow request but log warning

    async def sadd(self, key: str, *values: Any) -> int:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.sadd(key, *values))
        except Exception as e:
            await self._handle_error(e)
            return 0

    async def scard(self, key: str) -> int:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.scard(key))
        except Exception as e:
            await self._handle_error(e)
            return 0

    async def smembers(self, key: str) -> set:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.smembers(key))
        except Exception as e:
            await self._handle_error(e)
            return set()
    async def set(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.set(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def exists(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.exists(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def delete(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.delete(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def hset(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.hset(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def hget(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.hget(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def hgetall(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.hgetall(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def expire(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.expire(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    def lock(self, *args, **kwargs):
        if self._client:
            return self._client.lock(*args, **kwargs)
        return None

    async def aclose(self):
        if self._client:
            await self._maybe_await(self._client.aclose())
            self._client = None

# Singleton Instances
redis_client = redis.from_url(URL, **OPTS)
async_redis_client = ResilientAsyncRedis(URL, OPTS)

def verify_redis_connection():
    try:
        redis_client.ping()
        logger.info("✅ [REDIS] Sync Pulse: OK.")
        return True
    except AuthenticationError:
        logger.error("❌ [REDIS] Sync Auth Failed!")
        return False
    except Exception as e:
        logger.error(f"❌ [REDIS] Sync Error: {e}")
        return False

@asynccontextmanager
async def resource_lock(lock_key: str, lease_time: int = 10, wait_time: float = 5.0) -> AsyncGenerator[bool, None]:
    start = time.time()
    lock_id = f"lock:{lock_key}"
    acquired = False
    
    while time.time() - start < wait_time:
        try:
            client = await async_redis_client.get_client()
            res = await async_redis_client._maybe_await(client.set(lock_id, "id_nexus", ex=lease_time, nx=True))
            if res:
                acquired = True; break
        except Exception: break
        await asyncio.sleep(0.1)

    try: yield acquired
    finally:
        if acquired:
            try: 
                client = await async_redis_client.get_client()
                await async_redis_client._maybe_await(client.delete(lock_id))
            except: pass

if __name__ == "__main__":
     logging.basicConfig(level=logging.INFO)
     verify_redis_connection()

