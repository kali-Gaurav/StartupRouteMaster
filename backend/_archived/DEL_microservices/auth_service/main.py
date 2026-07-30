
import os
import time
import logging
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Depends, Body, status
from shared.config import Config
from shared.logging import setup_logging
from shared.auth import SharedAuthManager
from database.session import get_db
from sqlalchemy.orm import Session
import redis.asyncio as redis
from typing import Optional as OptionalType

# Shared imports setup
import sys
from pathlib import Path
shared_path = str(Path(__file__).resolve().parent.parent)
if shared_path not in sys.path:
    sys.path.append(shared_path)

setup_logging("auth-service")
logger = logging.getLogger("auth-service")

app = FastAPI(title="RouteMaster Auth Service")

# Redis for Rate Limiting
redis_client: OptionalType[redis.Redis] = None

@app.on_event("startup")
async def startup():
    global redis_client
    logger.info("🔐 Auth Service: Initializing Redis connection...")
    try:
        redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
        if redis_client:
            redis_client.ping()
        logger.info("✅ Auth Service: Redis connected.")
    except Exception as e:
        logger.error(f"❌ Auth Service: Redis connection failed: {e}")

# --- DEPENDENCIES ---
def get_auth_manager(db: Session = Depends(get_db)):
    return SharedAuthManager(db, redis_client)

# --- ROUTES ---

@app.post("/api/v1/auth/refresh")
async def refresh_token(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    auth_manager: SharedAuthManager = Depends(get_auth_manager)
):
    """
    [CONSOLIDATED] Refresh Token Rotation via Shared Logic.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not await auth_manager.check_rate_limit(f"refresh:{client_ip}", limit=10, window=60):
        raise HTTPException(status_code=429, detail="Too many refresh attempts")

    try:
        # Use consolidated SharedAuthManager for refresh
        if not auth_manager.supabase or not hasattr(auth_manager.supabase, 'auth'):
            raise HTTPException(status_code=500, detail="Auth service misconfigured")
        resp = auth_manager.supabase.auth.refresh_session(refresh_token)
        if not resp or not hasattr(resp, 'session') or not resp.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Type narrow the session
        assert resp.session is not None, "Session must not be None"
        sb_session = resp.session
        sb_user = sb_session.user
        
        # Sync user data across systems
        user = auth_manager.sync_user(sb_user)
        
        # Anomaly detection & Tracking
        is_suspicious = await auth_manager.detect_anomaly(user.id, request)
        auth_manager.track_session(user.id, request, sb_session.refresh_token)
        
        return {
            "access_token": sb_session.access_token,
            "refresh_token": sb_session.refresh_token,
            "expires_in": sb_session.expires_in,
            "is_suspicious": is_suspicious
        }
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        raise HTTPException(status_code=401, detail="Refresh failed")

@app.get("/api/v1/auth/sessions")
async def get_sessions(
    request: Request,
    auth_manager: SharedAuthManager = Depends(get_auth_manager)
):
    """List all active sessions for the user."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(status_code=401)
    
    sb_user = auth_manager.verify_jwt(token)
    user = auth_manager.sync_user(sb_user)
    
    sessions = auth_manager.get_active_sessions(user.id)
    return {
        "sessions": [
            {
                "id": s.id,
                "device": s.device_info,
                "ip": s.ip_address,
                "last_seen": s.last_seen_at.isoformat()
            } for s in sessions
        ]
    }

@app.post("/api/v1/auth/logout-all")
async def global_logout(
    request: Request,
    auth_manager: SharedAuthManager = Depends(get_auth_manager)
):
    """Invalidate all active sessions across the system."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(status_code=401)
    
    sb_user = auth_manager.verify_jwt(token)
    user = auth_manager.sync_user(sb_user)
    
    revoked_count = auth_manager.revoke_all_sessions(user.id)
    client_host = request.client.host if request.client else "unknown"
    auth_manager.log_audit(user.id, "GLOBAL_LOGOUT", reason=f"IP: {client_host}")
    
    return {"status": "success", "revoked_count": revoked_count}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}
