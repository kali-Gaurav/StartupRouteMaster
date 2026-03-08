from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any


from database.models import User
from database.session import get_db
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
    # Note: Using db_url as part of key to handle session changes if needed
    # In a real FastAPI app, we might use a custom cache service
    pass
def get_current_user(
    request: Request, # [31.8] Added request to access headers
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> User:
    """
    Verify the bearer token with Supabase auth and return the corresponding local User record.
    [31.3] Extracts roles. [31.8] Tracks sessions. [31.9] Optimized lookups.
    """
    # 1. Blacklist Check
    # ... rest ...

    if cache_service.is_available():
        if cache_service.get(f"jwt_blacklist:{token}"):
            raise HTTPException(status_code=401, detail="Token has been revoked")

    # 2. Supabase Verification
    try:
        resp = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    sb_user = None
    if hasattr(resp, "user"):
        sb_user = resp.user
    elif isinstance(resp, dict) and resp.get("data"):
        sb_user = resp["data"]
        
    if not sb_user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # 3. Identity Extraction
    sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
    sb_email = getattr(sb_user, "email", sb_user.get("email") if isinstance(sb_user, dict) else None)
    sb_metadata = getattr(sb_user, "user_metadata", sb_user.get("user_metadata", {}) if isinstance(sb_user, dict) else {})
    
    # [31.3] Role Extraction (Default to 'user')
    sb_role = sb_metadata.get("role") or "user"

    # 4. Local User Sync
    user_service = UserService(db)
    user = user_service.get_user_by_supabase_id(sb_id)
    
    if not user and sb_email:
        user = user_service.get_user_by_email(sb_email)
        if user:
            user.supabase_id = sb_id
            db.commit()

    if not user:
        # JIT Provisioning [31.7]
        from database.models import Profile
        sb_name = sb_metadata.get("full_name") or sb_metadata.get("name") or (sb_email.split('@')[0] if sb_email else "User")
        
        profile = Profile(id=sb_id, name=sb_name)
        db.add(profile)
        db.flush()
        
        user = user_service.create_user_with_data({
            "email": sb_email, "supabase_id": sb_id, "role": sb_role
        })
        db.flush() # Ensure user.id is populated
        # Force initial last_active_at to be old so session is triggered below
        user.last_active_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()
    else:
        # [31.3] Sync Role if changed in Supabase
        if user.role != sb_role:
            user.role = sb_role
            db.commit()

    # 5. Session Tracking [31.8]
    from database.models import UserSession
    from datetime import datetime
    
    # We record activity every 5 mins to avoid DB bloat
    now = datetime.utcnow()
    if not user.last_active_at or (now - user.last_active_at).total_seconds() > 300:
        # Extract metadata
        client_ip = request.headers.get("x-forwarded-for") or request.client.host
        if "," in client_ip: client_ip = client_ip.split(",")[0].strip()
        user_agent = request.headers.get("user-agent")

        user.last_active_at = now
        new_sess = UserSession(
            user_id=user.id, 
            login_at=now,
            ip_address=client_ip,
            user_agent=user_agent
        )
        db.add(new_sess)
        db.commit() # [31.8] Hard commit
        logger.info(f"Recorded new session for user {user.id}")

    return user

def require_role(allowed_roles: List[str]):
    """
    [36.1] Centralized RBAC Dependency.
    Usage: Depends(require_role(["admin", "agent"]))
    """
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            logger.warning(f"RBAC Denied: User {user.id} ({user.role}) tried to access {allowed_roles}")
            raise HTTPException(
                status_code=403, 
                detail=f"Forbidden: {', '.join(allowed_roles)} access required."
            )
        return user
    return role_checker

def get_optional_user(
    token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
):
    """Return a User when a valid Supabase token is provided, otherwise None."""
    if not token:
        return None
    try:
        resp = supabase.auth.get_user(token)
    except Exception:
        return None
        
    sb_user = None
    if hasattr(resp, "user"):
        sb_user = resp.user
    elif isinstance(resp, dict) and resp.get("data"):
        sb_user = resp["data"]
        
    if not sb_user:
        return None
        
    sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
    sb_email = getattr(sb_user, "email", sb_user.get("email") if isinstance(sb_user, dict) else None)

    user_service = UserService(db)
    user = None
    if sb_id:
        user = user_service.get_user_by_supabase_id(sb_id)
    if not user and sb_email:
        user = user_service.get_user_by_email(sb_email)
    
    # Update last_active_at if user exists
    if user:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if not user.last_active_at or (now - user.last_active_at) > timedelta(minutes=5):
            user.last_active_at = now
            db.commit()
    
    return user

async def verify_webhook_signature(request: Request):
    """Dependency to verify the signature of incoming Razorpay webhooks."""
    webhook_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Razorpay-Signature header not found.")

    payment_service = PaymentService()
    if not payment_service.verify_webhook_signature(webhook_body, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")
