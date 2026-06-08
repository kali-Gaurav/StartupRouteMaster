from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from database.models import Profile, User
from database.session import get_async_auth_db, get_db
from services.multi_layer_cache import multi_layer_cache
from utils.crypto import encrypt_pii
from core.auth.firebase_client import lazy_init, is_ready

logger = logging.getLogger(__name__)

# Attempt Firebase init at import time (non-fatal)
_firebase_ready = lazy_init()
if _firebase_ready:
    logger.info("🔥 dependencies.py: Firebase Admin SDK ready for token verification.")
else:
    logger.warning(
        "⚠️  dependencies.py: Firebase Admin SDK NOT ready. "
        "Protected routes will return 500 until GOOGLE_APPLICATION_CREDENTIALS is set."
    )



def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")
    return token.strip()


def _decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a Firebase ID token using the Admin SDK."""
    if not is_ready():
        logger.error(
            "Firebase Admin SDK not initialized. Set GOOGLE_APPLICATION_CREDENTIALS."
        )
        raise HTTPException(
            status_code=500,
            detail="Server authentication is not configured. Contact the administrator.",
        )
    try:
        from core.auth.firebase_client import get_auth
        firebase_auth = get_auth()
        decoded = firebase_auth.verify_id_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        # Distinguish common Firebase errors for clear client messages
        exc_type = type(exc).__name__
        if "ExpiredIdToken" in exc_type or "expired" in str(exc).lower():
            raise HTTPException(status_code=401, detail="Token expired.")
        if "RevokedIdToken" in exc_type or "revoked" in str(exc).lower():
            raise HTTPException(status_code=401, detail="Token has been revoked.")
        logger.warning("Firebase JWT validation failed [%s]: %s", exc_type, exc)
        raise HTTPException(status_code=401, detail="Could not validate credentials.")

    firebase_uid = decoded.get("uid")
    email = decoded.get("email")
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid token payload.")
    return {
        "sub": firebase_uid,
        "email": email or "",
        "name": decoded.get("name"),
        "picture": decoded.get("picture"),
        "email_verified": decoded.get("email_verified", False),
    }


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
        "firebase_uid": getattr(user, "firebase_uid", None),
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

    firebase_uid = payload["sub"]
    email = payload.get("email", "")
    cache_key = f"auth:user:{firebase_uid}"

    try:
        cached_user_data = await multi_layer_cache.get(cache_key)
    except Exception as exc:
        logger.warning("User cache lookup failed for %s: %s", firebase_uid, exc)
        cached_user_data = None

    if cached_user_data:
        return _hydrate_cached_user(cached_user_data)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    try:
        # Try to find user by firebase_uid field
        result = await db.execute(
            select(User)
            .filter(User.firebase_uid == firebase_uid)
            .options(selectinload(User.profile))
        )
        user = result.scalars().first()

        if not user:
            user = User(firebase_uid=firebase_uid, email=encrypt_pii(email), role="user")
            db.add(user)
            await db.flush()
            db.add(Profile(id=firebase_uid, user_id=user.id))
            await db.commit()
            result = await db.execute(
                select(User).filter(User.id == user.id).options(selectinload(User.profile))
            )
            user = result.scalars().first()
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Authentication sync failed for %s.", firebase_uid)
        raise HTTPException(status_code=503, detail="Authentication backend unavailable.") from exc

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    try:
        await multi_layer_cache.put(cache_key, _serialize_user(user), ttl=600)
    except Exception as exc:
        logger.warning("User cache write failed for %s: %s", firebase_uid, exc)

    return user


async def get_route_engine():
    from services.jit_manager import jit_manager

    await jit_manager.ensure_ready("GRAPH")
    from core.route_engine import get_route_engine

    return get_route_engine()


__all__ = ["get_current_user", "get_route_engine", "get_db"]
