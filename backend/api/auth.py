from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
import logging

from database.session import get_db
from database.models import User
from microservices.shared.auth import SharedAuthManager
from api.dependencies import get_current_user, oauth2_scheme_optional
from utils.limiter import limiter
from services.multi_layer_cache import multi_layer_cache

from jose import jwt
from datetime import datetime
from database.config import Config

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    """
    [Task 10 Upgrade] Logout using AuthServiceProvider.
    Blacklists the token in Redis and logs the audit event.
    """
    if not token:
        return {"status": "success", "message": "Already logged out."}
    
    try:
        from core.container import container
        auth_service = await container.get("auth")
        
        # Calculate remaining TTL for the token
        try:
            payload = jwt.decode(
                token, 
                Config.SUPABASE_JWT_SECRET, 
                algorithms=["HS256"], 
                options={"verify_aud": False}
            )
            exp = payload.get("exp")
            if exp:
                now = datetime.utcnow().timestamp()
                ttl = int(exp - now)
                if ttl > 0:
                    cache = await container.get("cache")
                    if cache and cache.redis:
                        await cache.redis.set(f"auth:blacklist:{token}", "revoked", ex=ttl)
                        logger.info(f"Token blacklisted for {ttl}s")
                    
                    user_id = payload.get("sub")
                    if user_id:
                        await auth_service.log_auth_event(user_id, "LOGOUT", request)
        except Exception as e:
            logger.warning(f"Logout cleanup warning: {e}")

        return {"status": "success", "message": "Logged out successfully."}
    except Exception as e:
        logger.error(f"Logout execution error: {e}")
        return {"status": "success", "message": "Logged out successfully."}
