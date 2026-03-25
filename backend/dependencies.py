import logging
import sys
import os
import time
import asyncio
from functools import lru_cache
from typing import Union, Optional, Dict

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

# Ensure correct pathing
sys.path.insert(0, os.path.dirname(__file__))

from database.session import SessionUser, get_auth_db, get_db, get_async_auth_db
from database.models import User, Profile
from config import Config
from utils.crypto import encrypt_pii
from services.multi_layer_cache import multi_layer_cache

logger = logging.getLogger(__name__)

# --- REDIS SESSION CACHE (Task 15 / 19) ---
# Replaces local _user_cache with high-performance, evicting Redis store via multi_layer_cache.

# ============================================================================
# AUTHENTICATION (Upgraded - Task 5 & Task 19)
# ============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None), 
    db: AsyncSession = Depends(get_async_auth_db)
) -> User:
    """
    Task 19: FAANG-Level Async Auth Pipeline.
    Includes Redis Multi-Layer Caching and non-blocking AsyncSession lookups.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "")
    
    # 1. JWT Validation
    try:
        secret = Config.SUPABASE_JWT_SECRET
        if not secret:
            logger.error("SUPABASE_JWT_SECRET not set in Config")
            raise HTTPException(status_code=500, detail="Server Configuration Error")
            
        payload = jwt.decode(
            token, 
            secret, 
            algorithms=["HS256"], 
            audience="authenticated",
            options={"verify_exp": True}
        )
        
        supabase_id = payload.get("sub")
        email = payload.get("email")
        
        if not supabase_id or not email:
             raise HTTPException(status_code=401, detail="Invalid Token Payload")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.JWTError as e:
        logger.warning(f"JWT Decode Error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception as e:
        logger.error(f"Unexpected Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # 2. Redis-Backed Multi-Layer Cache Check
    cache_key = f"auth:user:{supabase_id}"
    cached_user_data = await multi_layer_cache.get(cache_key)
    
    if cached_user_data:
        # Rehydrate User object with profile
        profile_data = cached_user_data.pop("profile", None)
        user = User(**cached_user_data)
        if profile_data:
            user.profile = Profile(**profile_data)
        return user

    # 3. Async Database Lookup & Sync
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    async def get_or_create_user():
        try:
            result = await db.execute(
                select(User).filter(User.supabase_id == supabase_id).options(selectinload(User.profile))
            )
            user = result.scalars().first()
            
            if not user:
                logger.info(f"Creating encrypted local record for {supabase_id}")
                user = User(
                    supabase_id=supabase_id,
                    email=encrypt_pii(email),
                    role="user"
                )
                db.add(user)
                await db.flush()
                profile = Profile(id=supabase_id, user_id=user.id)
                db.add(profile)
                await db.commit()
                # Re-fetch to ensure profile is loaded correctly
                result = await db.execute(
                    select(User).filter(User.id == user.id).options(selectinload(User.profile))
                )
                user = result.scalars().first()
            return user
        except Exception as e:
            await db.rollback()
            logger.error(f"Auth sync failed: {e}")
            raise HTTPException(status_code=401, detail="Session Sync Failed")

    user = await get_or_create_user()
    
    # 4. Update Redis Cache (Serialize to dict including profile)
    user_data = {
        "id": user.id,
        "supabase_id": user.supabase_id,
        "email": user.email,
        "role": user.role,
        "is_verified": user.is_verified,
        "full_name": user.full_name,
        "profile": {
            "id": user.profile.id,
            "name": user.profile.name,
            "avatar_url": user.profile.avatar_url,
            "ai_memory": user.profile.ai_memory
        } if user.profile else None
    }
    await multi_layer_cache.put(cache_key, user_data, ttl=600) # 10 minutes cache
    return user

async def get_route_engine():
    """
    Task 19: Efficient Route Engine Injection.
    Uses JIT to ensure engine is ready without blocking thread.
    """
    from services.jit_manager import jit_manager
    await jit_manager.ensure_ready("GRAPH")
    from core.route_engine import route_engine
    return route_engine
