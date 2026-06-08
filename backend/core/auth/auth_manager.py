import logging
from typing import Optional
from sqlalchemy.orm import Session
from database.models import User
# Try to import from AuthServiceProvider if it exists, otherwise use a simplified version
try:
    from core.auth.provider import auth_service
except ImportError:
    auth_service = None

logger = logging.getLogger("core.auth.manager")

class AuthManager:
    """
    Bridge class for Auth management.
    """
    def __init__(self, db: Session):
        self.db = db

    async def get_user_from_token(self, token: str) -> Optional[User]:
        """
        Get user from token using AuthServiceProvider or direct DB lookup.
        """
        if auth_service:
            try:
                # We need a dummy request object or modify verify_token to be more flexible
                # For now, let's assume we can do a basic verification
                from firebase_admin import auth as firebase_auth
                decoded_token = firebase_auth.verify_id_token(token)
                uid = decoded_token.get("uid")
                if uid:
                    from sqlalchemy import select
                    result = self.db.execute(select(User).where(User.firebase_uid == uid))
                    return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                return None
        
        # Fallback simplified token check (for development/testing)
        # In a real app, this should be a robust JWT check
        return None

__all__ = ["AuthManager"]
