"""
Phase 1: Backend Auth Refresh Endpoint
Handles session refresh when access token expires.
"""

from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel
from typing import Optional
from core.auth.supabase_client import supabase
from database.config import Config
import logging

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int
    token_type: str = "Bearer"


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest = Body(...)
):
    """
    Refresh an expired access token using a refresh token.
    Supabase handles the token generation.
    """
    try:
        # Attempt to refresh using Supabase
        response = supabase.auth.refresh_session(request.refresh_token)
        
        if not response or not hasattr(response, 'session'):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        session = response.session
        
        return TokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in or 3600
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed. Please login again."
        )


@router.post("/logout")
async def logout(
    refresh_token: str = Body(..., embed=True)
):
    """
    Logout by invalidating the refresh token.
    Frontend should also clear localStorage tokens.
    """
    try:
        supabase.auth.sign_out()
        return {"status": "logged_out"}
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )
