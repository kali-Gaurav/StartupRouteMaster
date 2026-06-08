"""
User Session Manager
====================
Manages user sessions with Redis-backed state storage.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
import asyncio

from services.multi_layer_cache import multi_layer_cache
from .schemas import UserContext, UserState, IntentType
from .config import bot_config

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """User session data."""
    chat_id: int
    user_id: int
    context: UserContext
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    message_count: int = 0
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        # Use mode='json' if available (Pydantic 2)
        try:
            context_dict = self.context.model_dump(mode='json')
        except TypeError:
            # Fallback for Pydantic 1
            import json
            context_dict = json.loads(self.context.json())

        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "context": context_dict,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSession":
        """Create session from dictionary."""
        return cls(
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            context=UserContext(**data["context"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            message_count=data.get("message_count", 0),
            is_active=data.get("is_active", True)
        )


class UserSessionManager:
    """
    Manages user sessions with Redis persistence.
    Provides conversation state management and context tracking.
    """
    
    def __init__(self, prefix: str = "telegram_session:"):
        self.prefix = prefix
        self.ttl = bot_config.session_ttl_hours * 3600
        
        # Local cache for active sessions
        self._local_cache: Dict[str, UserSession] = {}
        self._cache_lock = asyncio.Lock()

    @property
    def redis(self):
        return multi_layer_cache.redis
        
        # Metrics
        self._metrics: deque = deque(maxlen=500)
        self._metrics_lock = asyncio.Lock()
        
        logger.info(f"UserSessionManager initialized with TTL: {self.ttl}s")
    
    def _get_key(self, chat_id: int) -> str:
        """Generate Redis key for session."""
        return f"{self.prefix}{chat_id}"
    
    async def get_session(
        self, 
        chat_id: int, 
        user_id: int
    ) -> UserSession:
        """
        Get or create a user session.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            
        Returns:
            UserSession instance
        """
        cache_key = self._get_key(chat_id)
        
        # Check local cache first
        async with self._cache_lock:
            if cache_key in self._local_cache:
                session = self._local_cache[cache_key]
                session.last_activity = datetime.utcnow()
                session.message_count += 1
                return session
        
        # Try Redis
        try:
            data = await self.redis.get(cache_key)
            if data:
                session = UserSession.from_dict(json.loads(data))
                session.last_activity = datetime.utcnow()
                session.message_count += 1
                
                # Update local cache
                async with self._cache_lock:
                    self._local_cache[cache_key] = session
                
                return session
        except Exception as e:
            logger.error(f"Error fetching session from Redis: {e}")
        
        # Create new session
        session = UserSession(
            chat_id=chat_id,
            user_id=user_id,
            context=UserContext(
                chat_id=chat_id,
                user_id=user_id,
                state=UserState.IDLE
            )
        )
        
        # Save session
        await self.save_session(session)
        
        return session
    
    async def save_session(self, session: UserSession) -> bool:
        """
        Save session to Redis and local cache.
        
        Args:
            session: UserSession to save
            
        Returns:
            True if saved successfully
        """
        cache_key = self._get_key(session.chat_id)
        
        try:
            # Update local cache
            async with self._cache_lock:
                self._local_cache[cache_key] = session
            
            # Save to Redis
            await self.redis.set(
                cache_key,
                json.dumps(session.to_dict()),
                ex=self.ttl
            )
            
            return True
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False
    
    async def update_context(
        self, 
        chat_id: int, 
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update specific fields in user context.
        
        Args:
            chat_id: Telegram chat ID
            updates: Dictionary of updates to apply
            
        Returns:
            True if updated successfully
        """
        session = await self.get_session(chat_id, 0)
        
        # Apply updates to context
        for key, value in updates.items():
            if hasattr(session.context, key):
                setattr(session.context, key, value)
        
        session.context.updated_at = datetime.utcnow()
        
        return await self.save_session(session)
    
    async def update_state(
        self, 
        chat_id: int, 
        state: UserState,
        intent: Optional[IntentType] = None
    ) -> bool:
        """
        Update user state.
        
        Args:
            chat_id: Telegram chat ID
            state: New UserState
            intent: Optional new intent
            
        Returns:
            True if updated successfully
        """
        return await self.update_context(chat_id, {
            "state": state.value,
            "intent": intent.value if intent else None
        })
    
    async def add_to_history(
        self, 
        chat_id: int, 
        entry: Dict[str, Any]
    ) -> bool:
        """
        Add entry to conversation history.
        
        Args:
            chat_id: Telegram chat ID
            entry: History entry to add
            
        Returns:
            True if added successfully
        """
        session = await self.get_session(chat_id, 0)
        
        # Add timestamp
        entry["timestamp"] = datetime.utcnow().isoformat()
        
        # Add to history (keep last 20 entries)
        session.context.history.append(entry)
        session.context.history = session.context.history[-20:]
        
        return await self.save_session(session)
    
    async def clear_session(self, chat_id: int) -> bool:
        """
        Clear a user session.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if cleared successfully
        """
        cache_key = self._get_key(chat_id)
        
        try:
            # Remove from local cache
            async with self._cache_lock:
                self._local_cache.pop(cache_key, None)
            
            # Remove from Redis
            await self.redis.delete(cache_key)
            
            logger.info(f"Session cleared for chat_id: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False
    
    async def get_context(self, chat_id: int) -> Optional[UserContext]:
        """
        Get user context without creating a session.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            UserContext or None
        """
        session = await self.get_session(chat_id, 0)
        return session.context
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions from local cache.
        
        Returns:
            Number of sessions cleaned
        """
        cleaned = 0
        now = datetime.utcnow()
        expiry_threshold = timedelta(seconds=self.ttl)
        
        async with self._cache_lock:
            expired_keys = []
            for key, session in self._local_cache.items():
                if now - session.last_activity > expiry_threshold:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._local_cache[key]
                cleaned += 1
        
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} expired sessions")
        
        return cleaned
    
    async def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        async with self._cache_lock:
            return len(self._local_cache)
    
    def get_metrics(self) -> dict:
        """Get session manager metrics."""
        return {
            "local_cache_size": len(self._local_cache),
            "ttl_seconds": self.ttl,
            "total_recorded": len(self._metrics)
        }


# Global instance
user_session_manager = UserSessionManager()
