import logging
import time
from typing import Optional, Dict, Any
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger("services.session_lock")

class SessionLockService:
    """
    [Group 4] Dynamic UI-State Persistence & Locking.
    Ensures that a user's selection is preserved across multi-page sessions
    and prevents concurrent agents from mutating the same booking state.
    """
    LOCK_PREFIX = "nexus:lock:route:"
    STATE_PREFIX = "nexus:state:user:"

    async def acquire_route_lock(self, user_id: str, route_id: str, ttl_seconds: int = 600) -> bool:
        """
        Attempts to lock a specific route for a user.
        Prevents 'double-booking' or race conditions during JIT verification.
        """
        lock_key = f"{self.LOCK_PREFIX}{route_id}"
        # We use the cache as a distributed lock (simplified)
        existing = await multi_layer_cache.get_raw(lock_key)
        
        if existing and existing != user_id:
            logger.warning(f"🔒 [LOCK] Route {route_id} is already held by another session.")
            return False
            
        await multi_layer_cache.set_raw(lock_key, user_id, ttl=ttl_seconds)
        logger.info(f"🔑 [LOCK] Route {route_id} secured for User {user_id}.")
        return True

    async def release_route_lock(self, route_id: str):
        """Manually releases a route lock."""
        lock_key = f"{self.LOCK_PREFIX}{route_id}"
        await multi_layer_cache.delete_raw(lock_key)

    async def persist_ui_state(self, user_id: str, state_data: Dict[str, Any]):
        """
        Hardens the logic that preserves a user's flight/train selection 
        across device handoffs (Sub-second restoration).
        """
        state_key = f"{self.STATE_PREFIX}{user_id}"
        # Store comprehensive UI shard: current filter, selected route, scroll pos, etc.
        await multi_layer_cache.set_raw(state_key, state_data, ttl=3600) # 1 hour
        logger.info(f"💾 [STATE] UI persistence shard stored for User {user_id}.")

    async def restore_ui_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Restores the last known state for a user."""
        state_key = f"{self.STATE_PREFIX}{user_id}"
        return await multi_layer_cache.get_raw(state_key)

# Global singleton
session_lock_service = SessionLockService()
