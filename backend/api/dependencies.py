"""
API Dependencies - Common dependencies for FastAPI routes.
Provides authentication, authorization, and other shared dependencies.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from database import get_db
from database.models import User
from core.auth.auth_manager import AuthManager


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the request.
    """
    auth_manager = AuthManager(db)
    
    # Try to get user from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await auth_manager.get_user_from_token(token)
        if user:
            return user
    
    # Try to get user from session or cookie
    # This is a simplified version - in production, you'd have more robust session handling
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    """
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


def require_role(required_role: str):
    """
    Dependency factory that requires a specific role.
    Usage: @requires_role("ADMIN")
    """
    async def role_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return user
    
    return role_checker


async def verify_webhook_signature(request: Request) -> bool:
    """
    Verify webhook signature for payment callbacks.
    """
    # This is a placeholder - implement actual signature verification
    return True


async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if available, without raising exception.
    """
    try:
        return await get_current_user(request, db)
    except:
        return None


from fastapi.security import OAuth2PasswordBearer

# OAuth2 scheme for token authentication - Optional mode
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

__all__ = [
    "get_current_user",
    "get_optional_user", 
    "require_role",
    "verify_webhook_signature",
    "get_current_user_optional",
    "oauth2_scheme_optional"
]