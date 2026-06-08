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
    
    from urllib.parse import urlparse, urlunparse, unquote, quote
    
    # 1. Standardize scheme and identify cloud providers
    is_cloud = any(p in url for p in ["upstash.io", "rediscloud.com", "redislabs.com"])
    
    # Correct scheme for cloud providers if they use redis:// but need rediss://
    if is_cloud and url.startswith("redis://"):
        url = url.replace("redis://", "rediss://", 1)
    
    parsed = urlparse(url)
    scheme = parsed.scheme or ("rediss" if is_cloud else "redis")
    
    # 2. Robust Credential Extraction
    # netloc can be 'user:pass@host:port' or ':pass@host:port' or 'pass@host:port'
    username = parsed.username
    password = parsed.password
    
    if "@" in parsed.netloc:
        auth_part = parsed.netloc.rsplit("@", 1)[0]
        if ":" in auth_part:
            u, p = auth_part.split(":", 1)
            username = unquote(u) if u else username
            password = unquote(p) if p else password
        else:
            # If no colon, and it's cloud, the auth part is likely the password
            if is_cloud and not username:
                username = "default"
                password = unquote(auth_part)
            elif not password:
                password = unquote(auth_part)

    # Upstash/RedisCloud specific normalization
    if is_cloud:
        if not username and password:
            username = "default"
        elif username and not password and username != "default":
            password = username
            username = "default"

    # 3. Rebuild netloc safely
    # We quote the password to ensure special characters don't break the URL string
    auth_str = ""
    if password:
        user_part = quote(username) if username else "default"
        pass_part = quote(password)
        auth_str = f"{user_part}:{pass_part}@"
    
    host_port = parsed.hostname or "localhost"
    if parsed.port:
        host_port += f":{parsed.port}"
    elif is_cloud and not parsed.port:
        # Default ports if missing
        pass # urlparse usually gets it if it's there
        
    new_url = f"{scheme}://{auth_str}{host_port}{parsed.path}"
    if parsed.query:
        new_url += f"?{parsed.query}"
    
    # Mask for logging
    masked_pass = "***" if password else ""
    masked_url = f"{scheme}://{username or 'default'}:{masked_pass}@{parsed.hostname or 'localhost'}:{parsed.port or 6379}{parsed.path}"
    logger.info(f"[REDIS:URL_VERIFY] Verified connection: {masked_url}")
    
    return new_url

URL = sanitize_redis_url(Config.REDIS_URL)

OPTS = {
    "decode_responses": True,
    "ssl_cert_reqs": "none",
    "socket_timeout": 1.0,
    "socket_connect_timeout": 1.0,
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
        self._memory_shard: Dict[str, Any] = {} # [Patent Upgrade: Virtual Shard Fallback]

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
                return self._memory_shard.get(key)

        try:
            client = await self.get_client()
            val = await self._maybe_await(client.get(key))
            self.consecutive_failures = 0
            if val is not None: self._memory_shard[key] = val
            return val
        except Exception as e:
            await self._handle_error(e)
            return self._memory_shard.get(key)

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

    async def incr(self, key: str, amount: int = 1) -> int:
        try:
            client = await self.get_client()
            res = await self._maybe_await(client.incr(key, amount))
            self._memory_shard[key] = int(self._memory_shard.get(key, 0)) + amount
            return res
        except Exception as e:
            await self._handle_error(e)
            # Fallback to local memory counter
            current = int(self._memory_shard.get(key, 0))
            self._memory_shard[key] = current + amount
            return self._memory_shard[key]

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
        key = args[0] if args else kwargs.get("name")
        val = args[1] if len(args) > 1 else kwargs.get("value")
        
        try:
            client = await self.get_client()
            res = await self._maybe_await(client.set(*args, **kwargs))
            if key: self._memory_shard[str(key)] = val
            return res
        except Exception as e:
            await self._handle_error(e)
            if key: self._memory_shard[str(key)] = val
            return True

    async def type(self, key: str) -> str:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.type(key))
        except Exception as e:
            await self._handle_error(e)
            return "none"

    async def keys(self, pattern: str = "*") -> list:
        try:
            client = await self.get_client()
            return await self._maybe_await(client.keys(pattern))
        except Exception as e:
            await self._handle_error(e)
            return []

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

    async def xadd(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.xadd(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def geoadd(self, key: str, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.geoadd(key, *args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def geopos(self, key: str, *members: str):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.geopos(key, *members))
        except Exception as e:
            await self._handle_error(e)

    async def geodist(self, key: str, member1: str, member2: str, unit: str = 'm'):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.geodist(key, member1, member2, unit))
        except Exception as e:
            await self._handle_error(e)

    async def geosearch(self, *args, **kwargs):
        try:
            client = await self.get_client()
            # Handle both old and new geosearch styles
            return await self._maybe_await(client.geosearch(*args, **kwargs))
        except Exception as e:
            # Fallback to georadius if geosearch is not available (older redis)
            try:
                client = await self.get_client()
                return await self._maybe_await(client.georadius(*args, **kwargs))
            except:
                await self._handle_error(e)

    async def expire(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.expire(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def lpush(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.lpush(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def lrange(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.lrange(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def sadd(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.sadd(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def srem(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.srem(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def smembers(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.smembers(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def scard(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.scard(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    async def zcard(self, *args, **kwargs):
        try:
            client = await self.get_client()
            return await self._maybe_await(client.zcard(*args, **kwargs))
        except Exception as e:
            await self._handle_error(e)

    def lock(self, *args, **kwargs):
        if self._client:
            return self._client.lock(*args, **kwargs)
        return None

    @asynccontextmanager
    async def pipeline(self, *args, **kwargs):
        """
        [RM-IF-702] Pipeline context manager for batch performance.
        """
        client = await self.get_client()
        async with client.pipeline(*args, **kwargs) as pipe:
            yield pipe

    def register_script(self, script_text: str):
        """
        [RM-IF-703] Register a Lua script for atomic operations.
        Returns a proxy that lazily initializes the real script object.
        """
        class ScriptProxy:
            def __init__(self, parent, text):
                self.parent = parent
                self.text = text
                self.real_script = None

            async def __call__(self, keys=None, args=None, client=None):
                if not self.real_script:
                    c = await self.parent.get_client()
                    self.real_script = c.register_script(self.text)
                try:
                    return await self.real_script(keys=keys, args=args, client=client)
                except Exception as e:
                    await self.parent._handle_error(e)
                    raise

        return ScriptProxy(self, script_text)

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

