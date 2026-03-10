import asyncio
import logging
import uuid
from typing import Optional
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class DistributedLock:
    """
    Task 10: Distributed Lock Handling.
    Ensures background tasks (like ETL or scrapers) don't run simultaneously 
    on multiple production instances.
    """
    def __init__(self, lock_name: str, timeout: int = 60):
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self.lock_id = str(uuid.uuid4())
        self._locked = False

    async def __aenter__(self):
        if not multi_layer_cache.redis:
            # Fallback for local dev without redis
            self._locked = True
            return self

        # Try to acquire lock
        # nx=True: Set only if key does not exist
        # ex=timeout: Expire after timeout seconds
        success = await multi_layer_cache.redis.set(
            self.lock_name, self.lock_id, ex=self.timeout, nx=True
        )
        
        if success:
            self._locked = True
            logger.info(f"🔒 Acquired lock: {self.lock_name}")
            return self
        else:
            self._locked = False
            logger.warning(f"🚫 Failed to acquire lock (already held): {self.lock_name}")
            return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._locked and multi_layer_cache.redis:
            # Lua script to safely release lock only if we own it
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await multi_layer_cache.redis.eval(script, 1, self.lock_name, self.lock_id)
            logger.info(f"🔓 Released lock: {self.lock_name}")
        self._locked = False

async def is_task_running(task_name: str) -> bool:
    """Quick check if a task is already locked by another instance."""
    if not multi_layer_cache.redis:
        return False
    return await multi_layer_cache.redis.exists(f"lock:{task_name}")
