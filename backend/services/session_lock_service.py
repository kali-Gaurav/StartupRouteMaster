import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("services.session_lock")

class SessionLockService:
    """
    [Group 4] Dynamic UI-State Persistence & Locking.
    Ensures that a user's selection is preserved across multi-page sessions
    and prevents concurrent agents from mutating the same booking state.
    """
    LOCK_PREFIX = "nexus:lock:route:"
    STATE_PREFIX = "nexus:state:user:"

    def __init__(self):
        self._session_locks: Dict[str, Dict[str, Any]] = {}
        self._lock_ttl_seconds = 600

    async def acquire_route_lock(self, user_id: str, route_id: str, ttl_seconds: int = 600) -> bool:
        """
        Attempts to lock a specific route for a user.
        Prevents 'double-booking' or race conditions during JIT verification.
        """
        lock_key = f"{self.LOCK_PREFIX}{route_id}"
        existing = self._session_locks.get(lock_key)

        if existing and existing.get("user_id") != user_id and time.time() < existing.get("expires_at", 0):
            logger.warning(f"🔒 [LOCK] Route {route_id} is already held by another session.")
            return False

        self._session_locks[lock_key] = {
            "user_id": user_id,
            "expires_at": time.time() + ttl_seconds,
        }
        logger.info(f"🔑 [LOCK] Route {route_id} secured for User {user_id}.")
        return True

    async def release_route_lock(self, route_id: str):
        """Manually releases a route lock."""
        lock_key = f"{self.LOCK_PREFIX}{route_id}"
        self._session_locks.pop(lock_key, None)

    async def persist_ui_state(self, user_id: str, state_data: Dict[str, Any]):
        """
        Hardens the logic that preserves a user's flight/train selection 
        across device handoffs (Sub-second restoration).
        """
        state_key = f"{self.STATE_PREFIX}{user_id}"
        self._session_locks[state_key] = {
            "state_data": state_data,
            "expires_at": time.time() + 3600,
        }
        logger.info(f"💾 [STATE] UI persistence shard stored for User {user_id}.")

    async def restore_ui_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Restores the last known state for a user."""
        state_key = f"{self.STATE_PREFIX}{user_id}"
        data = self._session_locks.get(state_key)
        if data and time.time() < data.get("expires_at", 0):
            return data.get("state_data")
        return None

    async def initialize_lock(self, session_code: str, user_id: str, booking_id: Optional[str] = None, ttl_seconds: int = 600) -> bool:
        """Initialize a payment session lock for a user."""
        expires_at = time.time() + ttl_seconds
        self._session_locks[session_code] = {
            "user_id": user_id,
            "booking_id": booking_id,
            "expires_at": expires_at,
            "last_heartbeat": time.time()
        }
        logger.info(f"[SESSION_LOCK] Initialized lock for session {session_code}")
        return True

    async def record_heartbeat(self, session_code: str) -> bool:
        """Record a heartbeat for an active payment session."""
        lock = self._session_locks.get(session_code)
        if not lock:
            return False
        if time.time() > lock["expires_at"]:
            self._session_locks.pop(session_code, None)
            return False

        lock["last_heartbeat"] = time.time()
        lock["expires_at"] = time.time() + self._lock_ttl_seconds
        logger.debug(f"[SESSION_LOCK] Heartbeat received for session {session_code}")
        return True

class SearchSessionManager:
    """In-memory search session persistence for chat and search workflows."""

    _search_contexts: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def save_search_context(cls, user_id: str, search_id: str, context: Dict[str, Any]) -> None:
        cls._search_contexts[str(user_id)] = {
            "search_id": search_id,
            "context": context,
            "saved_at": time.time()
        }
        logger.info(f"[SEARCH_SESSION] Saved search context for user {user_id}")

    @classmethod
    def get_search_context(cls, user_id: str) -> Optional[Dict[str, Any]]:
        stored = cls._search_contexts.get(str(user_id))
        return stored.get("context") if stored else None

    @classmethod
    def update_ghost_results(cls, user_id: str, ghost_result: Dict[str, Any]) -> None:
        stored = cls._search_contexts.get(str(user_id))
        if stored and isinstance(stored.get("context"), dict):
            stored["context"]["ghost_result"] = ghost_result
            stored["context"]["ghost_updated_at"] = time.time()
            logger.info(f"[SEARCH_SESSION] Updated ghost results for user {user_id}")

# Global singleton
session_lock_service = SessionLockService()
