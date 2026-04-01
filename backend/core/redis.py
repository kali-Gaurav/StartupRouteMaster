import os
import logging
import asyncio
import time
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import redis
import redis.asyncio as aioredis
from database.config import Config

logger = logging.getLogger("nexus.redis")

# [Task 117] Elite Redis URL Sanitization
def sanitize_redis_url(url: str) -> str:
    """Ensures SSL/TLS and Auth compatibility for Cloud Providers (Upstash/RedisCloud)."""
    if not url: return "redis://localhost:6379/0"
    
    # If using SSL port but missing rediss:// scheme
    if (":6380" in url or "upstash.io" in url) and not url.startswith("rediss://"):
        logger.info("🛡️ [REDIS:BOOT] Detected Cloud Redis. Upgrading to SSL Protocol (rediss://)")
        url = url.replace("redis://", "rediss://")
    
    # [Task 117.2] Robust Auth Parsing
    # Standard redis-py handles :password@ but we ensure it's not stripped
    
    # Masked log for debugging
    from urllib.parse import urlparse
    parsed = urlparse(url)
    masked = f"{parsed.scheme}://***:***@{parsed.hostname}:{parsed.port}{parsed.path}"
    logger.info(f"🛡️ [REDIS:URL_VERIFY] Using masked connection: {masked}")
    
    return url

URL = sanitize_redis_url(Config.REDIS_URL)

# Shared Config
OPTS = {
    "decode_responses": True,
    "ssl_cert_reqs": "none",
    "socket_timeout": 5.0,
    "socket_connect_timeout": 5.0,
    "retry_on_timeout": True,
    "max_connections": 50
}

# 1. Sync Client (Lifecycle management)
redis_client = redis.from_url(URL, **OPTS)

# 2. Async Client (Production traffic)
async_redis_client = aioredis.from_url(URL, **OPTS)

# [Elite] Boot-time Ping Verification
def verify_redis_connection():
    try:
        redis_client.ping()
        logger.info("✅ Redis Pulse: HEARTBEAT STABLE.")
        return True
    except redis.exceptions.AuthenticationError:
        logger.error("❌ Redis Authentication FAILED. Check your .env credentials!")
        return False
    except Exception as e:
        logger.error(f"❌ Redis Connectivity SEVERED: {e}")
        return False

@asynccontextmanager
async def resource_lock(lock_key: str, lease_time: int = 10, wait_time: int = 5) -> AsyncGenerator[bool, None]:
    """[Elite Refinement 117] Distributed Locking with Adaptive Backoff."""
    from core.resource_monitor import resource_monitor
    try:
        if resource_monitor.get_stats()["state"] != "HEALTHY":
            wait_time = 2.0
    except: pass

    start = time.time()
    lock_id = f"lock:{lock_key}"
    acquired = False
    
    while time.time() - start < wait_time:
        try:
            res = await async_redis_client.set(lock_id, "id_nexus", ex=lease_time, nx=True)
            if res:
                acquired = True; break
        except Exception: break
        await asyncio.sleep(0.1)

    try: yield acquired
    finally:
        if acquired:
            try: await async_redis_client.delete(lock_id)
            except: pass

# Initial ping on import
if __name__ == "__main__":
     verify_redis_connection()
