from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database.models import User, UserSession
from database.session import get_db
from database.config import Config
from services.user_service import UserService
from services.payment_service import PaymentService
from utils.security import decode_access_token, credentials_exception
from services.cache_service import cache_service

# supabase client used for token validation
from core.auth.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
# Optional OAuth2 scheme for endpoints that may accept anonymous requests
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


from functools import lru_cache

@lru_cache(maxsize=128)
def _get_cached_user_id(supabase_id: str, db_url: str):
    """[31.9] Internal helper for cached user lookup by ID."""
    pass

def get_current_user(
    request: Request, # [31.8] Added request to access headers
    token: str = Depends(oauth2_scheme_optional), 
    db: Session = Depends(get_db)
) -> User:
    """
    Verify the bearer token with Supabase auth and return the corresponding local User record.
    [31.3] Extracts roles. [31.8] Tracks sessions. [31.9] Optimized lookups.
    """
    # 1. Task 11.13: Blacklist Check (MUST BE BEFORE BYPASS TO ENSURE REVOCATION)
    if token and cache_service.is_available():
        if cache_service.get(f"auth:blacklist:{token}") or cache_service.get(f"jwt_blacklist:{token}"):
            logger.warning(f"Blocked revoked token: {token[:10]}...")
            raise HTTPException(status_code=401, detail="Session has been terminated")

    # 2. Task 31.2: Dev-only bypass for deep logic verification
    if Config.ENVIRONMENT == "development" and request.headers.get("X-Dev-Bypass") == "TRUE":
        # Return a mock admin user for deep logic testing
        return User(id="dev-admin", email="dev@routemaster.io", role="admin")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")

    # 3. Supabase Verification
    try:
        # Task 31.2: Strict Supabase JWT Validation
        resp = supabase.auth.get_user(token)
        sb_user = None
        if hasattr(resp, "user") and resp.user:
            sb_user = resp.user
        elif isinstance(resp, dict) and resp.get("user"):
            sb_user = resp["user"]
        elif hasattr(resp, "data") and resp.data:
            sb_user = resp.data
            
        if not sb_user:
            logger.warning(f"Supabase returned empty user for token: {token[:10]}...")
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    except Exception as e:
        logger.error(f"Supabase Auth Error: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

    # 4. Identity Extraction
    sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
    sb_email = getattr(sb_user, "email", sb_user.get("email") if isinstance(sb_user, dict) else None)
    sb_metadata = getattr(sb_user, "user_metadata", sb_user.get("user_metadata", {}) if isinstance(sb_user, dict) else {})
    sb_role = sb_metadata.get("role") or "user"

    # 5. Local User Sync
    user_service = UserService(db)
    user = user_service.get_user_by_supabase_id(sb_id)
    
    if not user and sb_email:
        user = user_service.get_user_by_email(sb_email)
        if user:
            user.supabase_id = sb_id
            db.commit()

    if not user:
        from database.models import Profile
        sb_name = sb_metadata.get("full_name") or sb_metadata.get("name") or (sb_email.split('@')[0] if sb_email else "User")
        profile = Profile(id=sb_id, name=sb_name)
        db.add(profile)
        db.flush()
        user = user_service.create_user_with_data({
            "email": sb_email, "supabase_id": sb_id, "role": sb_role
        })
        db.flush()
        user.last_active_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()
    else:
        if user.role != sb_role:
            user.role = sb_role
            db.commit()

    # 6. Session Tracking [31.8]
    now = datetime.utcnow()
    if not user.last_active_at or (now - user.last_active_at).total_seconds() > 300:
        client_ip = request.headers.get("x-forwarded-for") or request.client.host
        if "," in client_ip: client_ip = client_ip.split(",")[0].strip()
        user_agent = request.headers.get("user-agent")
        user.last_active_at = now
        new_sess = UserSession(user_id=user.id, login_at=now, ip_address=client_ip, user_agent=user_agent)
        db.add(new_sess)
        db.commit()
        logger.info(f"Recorded new session for user {user.id}")

    # 7. Verification Enforcement
    # Allow bypass in dev if configured, otherwise require is_verified
    if not user.is_verified and Config.ENVIRONMENT != "development":
        logger.warning(f"Unverified access attempt by user {user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account verification required. Please check your email or phone for the OTP."
        )

    return user

def require_role(allowed_roles: List[str]):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            logger.warning(f"RBAC Denied: User {user.id} ({user.role}) tried to access {allowed_roles}")
            raise HTTPException(status_code=403, detail=f"Forbidden: {', '.join(allowed_roles)} access required.")
        return user
    return role_checker

def get_optional_user(token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    if not token: return None
    try:
        resp = supabase.auth.get_user(token)
        sb_user = getattr(resp, "user", resp.get("data") if isinstance(resp, dict) else None)
        if not sb_user: return None
        sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
        user_service = UserService(db)
        return user_service.get_user_by_supabase_id(sb_id)
    except: return None

async def verify_webhook_signature(request: Request):
    webhook_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature: raise HTTPException(status_code=400, detail="X-Razorpay-Signature header not found.")
    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(webhook_body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
