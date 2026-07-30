"""
User Service - User management for Telegram bot.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from database.models import User, UserSession

logger = logging.getLogger("user_service")


class UserService:
    """Service for user management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_telegram_id(
        self,
        telegram_id: str
    ) -> Optional[User]:
        """Get user by Telegram ID."""
        try:
            result = await self.db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by telegram ID: {e}")
            return None
    
    async def get_user_by_phone(
        self,
        phone: str
    ) -> Optional[User]:
        """Get user by phone number."""
        try:
            result = await self.db.execute(
                select(User).where(User.phone_number == phone)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by phone: {e}")
            return None
    
    async def get_user_by_id(
        self,
        user_id: str
    ) -> Optional[User]:
        """Get user by ID."""
        try:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    async def create_user(
        self,
        telegram_id: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None
    ) -> User:
        """Create a new user."""
        user = User(
            id=str(uuid.uuid4()),
            telegram_id=telegram_id,
            full_name=name,
            phone_number=phone,
            email=email,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        logger.info(f"Created user: {user.id} (Telegram: {telegram_id})")
        return user
    
    async def update_user(
        self,
        user_id: str,
        **kwargs
    ) -> Optional[User]:
        """Update user details."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.updated_at = datetime.now(timezone.utc)
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def get_or_create_user(
        self,
        telegram_id: str,
        name: Optional[str] = None,
        phone: Optional[str] = None
    ) -> User:
        """Get existing user or create new one."""
        user = await self.get_user_by_telegram_id(telegram_id)
        
        if user:
            # Update name if provided
            if name and name != user.full_name:
                await self.update_user(user.id, full_name=name)
                user.full_name = name
            return user
        
        return await self.create_user(telegram_id, name, phone)
    
    async def record_session(
        self,
        user_id: str,
        telegram_id: str,
        chat_id: int
    ) -> UserSession:
        """Record user session."""
        session = UserSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            telegram_id=telegram_id,
            chat_id=str(chat_id),
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        
        return session
    
    async def get_user_stats(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get user statistics."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return {}
        
        return {
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "name": user.full_name,
            "phone": user.phone_number,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "total_bookings": 0, # not on model
            "wallet_balance": user.credit_balance or 0.0
        }


# Removed singleton
# user_service = None

def get_user_service(db: AsyncSession) -> UserService:
    """Get or create user service instance."""
    return UserService(db)