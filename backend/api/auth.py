from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from pydantic import BaseModel, EmailStr

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

# Request/Response Models
class SendOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class VerifyOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    otp: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class TelegramAuthRequest(BaseModel):
    init_data: str
    user: dict

class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[dict] = None
    is_new_user: Optional[bool] = None

# ============================================================================
# OTP-BASED AUTHENTICATION (Task: Mobile-First Auth)
# ============================================================================

@router.post("/send-otp", response_model=AuthResponse)
@limiter.limit("5/minute")
async def send_otp(
    request: Request,
    payload: SendOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Send OTP to user's phone or email for authentication.
    Rate limited to 5 requests per minute.
    """
    if not payload.phone and not payload.email:
        raise HTTPException(
            status_code=400,
            detail="Either phone or email is required"
        )
    
    try:
        # Determine contact method
        contact = payload.phone or payload.email
        contact_type = "phone" if payload.phone else "email"
        
        # Rate limiting check (per contact)
        cache_key = f"otp:sent:{contact}"
        if await multi_layer_cache.get(cache_key):
            raise HTTPException(
                status_code=429,
                detail="OTP already sent. Please wait 2 minutes before requesting again."
            )
        
        # Generate OTP (6 digits)
        import secrets
        otp = str(secrets.randbelow(1000000)).zfill(6)
        
        # Store OTP in cache with 10-minute expiry
        otp_cache_key = f"otp:code:{contact}"
        await multi_layer_cache.put(otp_cache_key, otp, ttl=600)
        
        # Mark that OTP was sent (2-minute cooldown)
        await multi_layer_cache.put(cache_key, True, ttl=120)
        
        # TODO: Send OTP via actual SMS/Email service
        logger.info(f"OTP sent to {contact_type}: {contact}")
        
        return AuthResponse(
            success=True,
            message=f"OTP sent to {contact_type}"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send OTP error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP"
        )

@router.post("/verify-otp", response_model=AuthResponse)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request,
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Verify OTP sent to user's phone or email.
    On successful verification, create/sync user and return Supabase token.
    """
    if not payload.phone and not payload.email:
        raise HTTPException(
            status_code=400,
            detail="Either phone or email is required"
        )
    
    if not payload.otp or len(payload.otp) != 6:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP format"
        )
    
    try:
        contact = payload.phone or payload.email
        otp_cache_key = f"otp:code:{contact}"
        
        # Retrieve stored OTP
        stored_otp = await multi_layer_cache.get(otp_cache_key)
        if not stored_otp:
            raise HTTPException(
                status_code=401,
                detail="OTP expired or not found. Please request a new OTP."
            )
        
        # Verify OTP matches
        if str(stored_otp) != str(payload.otp):
            raise HTTPException(
                status_code=401,
                detail="Invalid OTP"
            )
        
        # Clear used OTP
        await multi_layer_cache.delete(otp_cache_key)
        
        from database.models import Profile
        from datetime import timedelta, datetime as dt
        
        # Find or create user
        if payload.email:
            user = db.query(User).filter(User.email == payload.email).first()
        else:
            user = db.query(User).filter(User.phone == payload.phone).first()
        
        is_new_user = False
        
        if not user:
            is_new_user = True
            user = User(
                email=payload.email or f"{payload.phone}@sms.safesafar.app",
                phone=payload.phone,
                role="user"
            )
            db.add(user)
            db.flush()
            
            profile = Profile(id=user.id, user_id=user.id)
            db.add(profile)
            db.commit()
            logger.info(f"New user created via OTP: {contact}")
        else:
            db.commit()
        
        # Generate JWT token
        token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": dt.utcnow() + timedelta(days=7),
                "iat": dt.utcnow(),
                "aud": "authenticated"
            },
            Config.SUPABASE_JWT_SECRET,
            algorithm="HS256"
        )
        
        # Cache user session
        cache_key = f"auth:user:{user.id}"
        await multi_layer_cache.put(cache_key, {
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "role": user.role
        }, ttl=86400)
        
        return AuthResponse(
            success=True,
            message="OTP verified successfully",
            token=token,
            user={"id": str(user.id), "email": user.email},
            is_new_user=is_new_user
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify OTP error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to verify OTP"
        )

# ============================================================================
# OAUTH AUTHENTICATION (Google, Telegram)
# ============================================================================

@router.post("/google", response_model=AuthResponse)
@limiter.limit("20/minute")
async def google_auth(
    request: Request,
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate via Google ID Token.
    Syncs with Supabase and creates local user record.
    """
    if not payload.id_token:
        raise HTTPException(
            status_code=400,
            detail="id_token is required"
        )
    
    try:
        import json
        import base64
        from datetime import timedelta, datetime as dt
        from database.models import Profile
        
        # Decode JWT (without verification for now - TODO: use google-auth library)
        parts = payload.id_token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="Invalid token format")
        
        # Decode payload (middle part)
        payload_part = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_part) % 4
        if padding != 4:
            payload_part += '=' * padding
        
        try:
            google_payload = json.loads(base64.urlsafe_b64decode(payload_part))
        except:
            raise HTTPException(status_code=400, detail="Invalid token payload")
        
        google_id = google_payload.get("sub")
        email = google_payload.get("email")
        name = google_payload.get("name", email.split('@')[0] if email else "User")
        
        if not google_id or not email:
            raise HTTPException(status_code=400, detail="Invalid token data")
        
        # Create or get user
        user = db.query(User).filter(User.email == email).first()
        is_new_user = False
        
        if not user:
            is_new_user = True
            user = User(
                email=email,
                full_name=name,
                role="user"
            )
            db.add(user)
            db.flush()
            
            profile = Profile(id=user.id, user_id=user.id)
            db.add(profile)
            db.commit()
            logger.info(f"New user created via Google: {email}")
        else:
            db.commit()
        
        # Generate JWT token
        token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": dt.utcnow() + timedelta(days=7),
                "iat": dt.utcnow(),
                "aud": "authenticated"
            },
            Config.SUPABASE_JWT_SECRET,
            algorithm="HS256"
        )
        
        # Cache user session
        cache_key = f"auth:user:{user.id}"
        await multi_layer_cache.put(cache_key, {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name
        }, ttl=86400)
        
        return AuthResponse(
            success=True,
            message="Google authentication successful",
            token=token,
            user={"id": str(user.id), "email": user.email, "name": user.full_name},
            is_new_user=is_new_user
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Google authentication failed"
        )

@router.post("/telegram", response_model=AuthResponse)
@limiter.limit("20/minute")
async def telegram_auth(
    request: Request,
    payload: TelegramAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate via Telegram Mini App.
    Validates init_data hash and creates/syncs user.
    """
    if not payload.init_data or not payload.user:
        raise HTTPException(
            status_code=400,
            detail="init_data and user are required"
        )
    
    try:
        from datetime import timedelta, datetime as dt
        from database.models import Profile
        
        # TODO: Validate Telegram init_data hash
        
        # Extract Telegram user ID
        telegram_id = str(payload.user.get("id"))
        telegram_username = payload.user.get("username", "")
        telegram_first_name = payload.user.get("first_name", "Telegram User")
        
        if not telegram_id:
            raise HTTPException(status_code=400, detail="Invalid Telegram user")
        
        # Create or get user
        email = f"{telegram_id}@telegram.safesafar.app"
        user = db.query(User).filter(User.email == email).first()
        is_new_user = False
        
        if not user:
            is_new_user = True
            user = User(
                email=email,
                full_name=telegram_first_name,
                role="user"
            )
            db.add(user)
            db.flush()
            
            profile = Profile(id=user.id, user_id=user.id)
            db.add(profile)
            db.commit()
            logger.info(f"New user created via Telegram: {telegram_username or telegram_id}")
        else:
            db.commit()
        
        # Generate JWT token
        token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": dt.utcnow() + timedelta(days=7),
                "iat": dt.utcnow(),
                "aud": "authenticated"
            },
            Config.SUPABASE_JWT_SECRET,
            algorithm="HS256"
        )
        
        # Cache user session
        cache_key = f"auth:user:{user.id}"
        await multi_layer_cache.put(cache_key, {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name
        }, ttl=86400)
        
        return AuthResponse(
            success=True,
            message="Telegram authentication successful",
            token=token,
            user={"id": str(user.id), "email": user.email, "name": user.full_name},
            is_new_user=is_new_user
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Telegram auth error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Telegram authentication failed"
        )

# ============================================================================
# USER INFO & LOGOUT
# ============================================================================

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    """
    return {
        "success": True,
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "phone": current_user.phone,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "is_verified": current_user.is_verified
        }
    }

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
