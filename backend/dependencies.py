from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from database.models import Profile, User
from database.session import get_async_auth_db, get_db
from services.multi_layer_cache import multi_layer_cache
from utils.crypto import encrypt_pii

logger = logging.getLogger(__name__)


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")
    return token.strip()


def _decode_token(token: str) -> Dict[str, Any]:
    secret = Config.SUPABASE_JWT_SECRET
    if not secret:
        logger.error("SUPABASE_JWT_SECRET is not configured.")
        raise HTTPException(status_code=500, detail="Server authentication is not configured.")

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired.") from exc
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Could not validate credentials.") from exc

    supabase_id = payload.get("sub")
    email = payload.get("email")
    if not supabase_id or not email:
        raise HTTPException(status_code=401, detail="Invalid token payload.")
    return payload


def _hydrate_cached_user(cached_user_data: Dict[str, Any]) -> User:
    payload = dict(cached_user_data)
    profile_data = payload.pop("profile", None)
    user = User(**payload)
    if profile_data:
        user.profile = Profile(**profile_data)
    return user


def _serialize_user(user: User) -> Dict[str, Any]:
    profile = getattr(user, "profile", None)
    profile_data = None
    if profile is not None:
        profile_data = {
            "id": profile.id,
            "name": profile.name,
            "avatar_url": profile.avatar_url,
            "ai_memory": profile.ai_memory,
            "user_id": profile.user_id,
        }

    return {
        "id": user.id,
        "supabase_id": user.supabase_id,
        "email": user.email,
        "role": user.role,
        "is_verified": user.is_verified,
        "full_name": user.full_name,
        "profile": profile_data,
    }


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_async_auth_db),
) -> User:
    token = _extract_bearer_token(authorization)
    payload = _decode_token(token)

    supabase_id = payload["sub"]
    email = payload["email"]
    cache_key = f"auth:user:{supabase_id}"

    try:
        cached_user_data = await multi_layer_cache.get(cache_key)
    except Exception as exc:
        logger.warning("User cache lookup failed for %s: %s", supabase_id, exc)
        cached_user_data = None

    if cached_user_data:
        return _hydrate_cached_user(cached_user_data)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    try:
        result = await db.execute(
            select(User)
            .filter(User.supabase_id == supabase_id)
            .options(selectinload(User.profile))
        )
        user = result.scalars().first()

        if not user:
            user = User(supabase_id=supabase_id, email=encrypt_pii(email), role="user")
            db.add(user)
            await db.flush()
            db.add(Profile(id=supabase_id, user_id=user.id))
            await db.commit()
            result = await db.execute(
                select(User).filter(User.id == user.id).options(selectinload(User.profile))
            )
            user = result.scalars().first()
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Authentication sync failed for %s.", supabase_id)
        raise HTTPException(status_code=503, detail="Authentication backend unavailable.") from exc

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    try:
        await multi_layer_cache.put(cache_key, _serialize_user(user), ttl=600)
    except Exception as exc:
        logger.warning("User cache write failed for %s: %s", supabase_id, exc)

    return user


async def get_route_engine():
    from services.jit_manager import jit_manager

    await jit_manager.ensure_ready("GRAPH")
    from core.route_engine import get_route_engine

    return get_route_engine()


__all__ = ["get_current_user", "get_route_engine", "get_db"]
