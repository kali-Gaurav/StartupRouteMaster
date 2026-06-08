import logging
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

class QueueWardenAgent:
    """
    [G1.1.3] System Builder Agent: Queue-Warden.
    Regulates the 'Thundering Herd' during peak booking events by limiting 
    concurrent checkout sessions per Train/Class.
    """
    def __init__(self):
        self.max_concurrent_checkouts = 5  # Configurable threshold
        self.lock_ttl_seconds = 45         # Max time allowed for checkout

    async def acquire_checkout_slot(self, train_number: str, class_code: str) -> bool:
        """
        Atomically increments the checkout counter for a specific resource.
        Returns True if slot is secured, False if queue is full.
        """
        if not multi_layer_cache.redis:
            logger.warning("⚠️ [WARDEN] Redis unavailable. Bypassing semaphore (Risk: High Concurrency).")
            return True

        key = f"warden:checkout:{train_number}:{class_code}"
        
        try:
            # 1. Atomic Increment
            current_slots = await multi_layer_cache.redis.incr(key)
            
            # 2. Set TTL on first entry to prevent zombie locks
            if current_slots == 1:
                await multi_layer_cache.redis.expire(key, self.lock_ttl_seconds)
            
            # 3. Admission Control
            if current_slots > self.max_concurrent_checkouts:
                logger.warning(f"🚫 [WARDEN] Queue Full for {train_number}-{class_code} ({current_slots}/{self.max_concurrent_checkouts})")
                # Auto-correction: decrement back if we block
                await multi_layer_cache.redis.decr(key)
                return False
                
            logger.info(f"🛡️ [WARDEN] Slot Secured for {train_number}-{class_code} ({current_slots}/{self.max_concurrent_checkouts})")
            return True
            
        except Exception as e:
            logger.error(f"🚨 [WARDEN] Semaphore Failure: {e}")
            return True # Fail open to prevent user blocking

    async def release_checkout_slot(self, train_number: str, class_code: str):
        """
        Atomically decrements the checkout counter.
        """
        if not multi_layer_cache.redis:
            return

        key = f"warden:checkout:{train_number}:{class_code}"
        try:
            val = await multi_layer_cache.redis.decr(key)
            # Ensure we don't go below zero
            if val < 0:
                await multi_layer_cache.redis.set(key, 0)
                await multi_layer_cache.redis.expire(key, 5)
            logger.info(f"🔓 [WARDEN] Slot Released for {train_number}-{class_code}")
        except Exception as e:
            logger.error(f"🚨 [WARDEN] Release Failure: {e}")

queue_warden = QueueWardenAgent()
