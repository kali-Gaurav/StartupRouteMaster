import os
import redis
from database.config import Config

# Initialize synchronous redis client
redis_client = redis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    max_connections=50 # Increased pool size
)

import redis.asyncio as aioredis
# Initialize async redis client
async_redis_client = aioredis.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    max_connections=50
)

import asyncio
import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

logger = logging.getLogger("routemaster.redis")

@asynccontextmanager
async def resource_lock(lock_key: str, lease_time: int = 10, wait_time: int = 5) -> AsyncGenerator[bool, None]:
    """
    Task 46: Distributed Locking Context Manager.
    Adaptive wait time based on system load.
    """
    # Adaptive wait (Task 46.3)
    from core.resource_monitor import resource_monitor
    if resource_monitor.get_stats()["state"] != "HEALTHY":
        wait_time = 2.0

    start = time.time()
    lock_id = f"lock:{lock_key}"
    acquired = False
    
    while time.time() - start < wait_time:
        try:
            res = await async_redis_client.set(lock_id, "1", ex=lease_time, nx=True)
            if res:
                acquired = True
                break
        except Exception: break
        await asyncio.sleep(0.1)

    try:
        yield acquired
    finally:
        if acquired:
            try: await async_redis_client.delete(lock_id)
            except: pass
