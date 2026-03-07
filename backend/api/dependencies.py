from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session


from database.models import User
from database.session import get_db
from services.user_service import UserService
from services.payment_service import PaymentService
from utils.security import decode_access_token, credentials_exception
from services.cache_service import cache_service

# supabase client used for token validation
from core.auth.supabase_client import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")
# Optional OAuth2 scheme for endpoints that may accept anonymous requests
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/users/token", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    Verify the bearer token with Supabase auth and return the corresponding
    local User record (creating a stub if it doesn't exist).  This keeps the
    existing codebase able to reference a SQLAlchemy `User` object while the
    authoritative authentication lives in Supabase.
    """
    # first check local blacklist (redis) if present; old tokens we rejected
    if cache_service.is_available():
        if cache_service.get(f"jwt_blacklist:{token}"):
            raise credentials_exception

    # verify against Supabase; the client method will raise or return error
    try:
        resp = supabase.auth.get_user(token)
    except Exception as e:
        raise credentials_exception
        
    sb_user = None
    if hasattr(resp, "user"):
        sb_user = resp.user
    elif isinstance(resp, dict) and resp.get("data"):
        sb_user = resp["data"]
        
    if not sb_user:
        raise credentials_exception

    # Extract user metadata cleanly
    sb_id = getattr(sb_user, "id", sb_user.get("id") if isinstance(sb_user, dict) else None)
    sb_email = getattr(sb_user, "email", sb_user.get("email") if isinstance(sb_user, dict) else None)
    
    # NEW: Extract metadata fields
    sb_metadata = getattr(sb_user, "user_metadata", sb_user.get("user_metadata", {}) if isinstance(sb_user, dict) else {})
    sb_name = sb_metadata.get("full_name") or sb_metadata.get("name") or (sb_email.split('@')[0] if sb_email else "User")
    sb_avatar = sb_metadata.get("avatar_url")
    sb_phone = sb_metadata.get("phone") or getattr(sb_user, "phone", None)

    user_service = UserService(db)
    user = None
    if sb_id:
        user = user_service.get_user_by_supabase_id(sb_id)
    
    if not user and sb_email:
        user = user_service.get_user_by_email(sb_email)
        if user and sb_id:
            user.supabase_id = sb_id
            db.commit()

    from database.models import Profile
    if not user:
        # Create everything
        profile = Profile(
            id=sb_id, 
            name=sb_name, 
            avatar_url=sb_avatar, 
            phone=sb_phone
        )
        db.add(profile)
        db.flush()
        
        user = user_service.create_user_with_data({
            "email": sb_email,
            "supabase_id": sb_id,
            "password_hash": "supabase_managed",
        })
    else:
        # SYNC: Update profile with latest metadata from Supabase
        profile = db.query(Profile).filter(Profile.id == sb_id).first()
        if profile:
            profile.name = sb_name
            profile.avatar_url = sb_avatar
            if sb_phone and not profile.phone:
                profile.phone = sb_phone
            db.commit()
            
    # Subtask 4.2: DAU Analytics - Update last_active_at with 5min cooldown
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    if not user.last_active_at or (now - user.last_active_at) > timedelta(minutes=5):
        user.last_active_at = now
        db.commit()

    return user


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
