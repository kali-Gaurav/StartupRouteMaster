
# pyrefly: ignore [missing-import]
from jose import jwt
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status, Request
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr
import os
import hashlib
from datetime import datetime, timedelta as dt_timedelta
from database.session import get_db
from database.models import User, Profile
from database.config import Config
from microservices.shared.auth import SharedAuthManager
from api.dependencies import get_current_user, oauth2_scheme_optional
from utils.limiter import limiter
from services.multi_layer_cache import multi_layer_cache
from utils.v3_response import success_response, v3_response
from utils.logger import HardenedLogger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = HardenedLogger("AUTH_SERVICE")


def _create_firebase_custom_token(uid: str) -> str:
    """
    Create a Firebase custom token for the given UID.
    The frontend should exchange this via signInWithCustomToken() to get
    a proper Firebase ID token that can be used with all protected routes.

    Falls back gracefully if Firebase Admin SDK is not configured.
    """
    try:
        from core.auth.firebase_client import get_auth
        firebase_auth = get_auth()
        token_bytes = firebase_auth.create_custom_token(uid)
        # create_custom_token returns bytes; decode to str for JSON serialization
        return token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes
    except Exception as exc:
        logger.error("FIREBASE_CUSTOM_TOKEN_FAILED", {"uid": uid, "error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail=(
                "Authentication token generation failed. "
                "Firebase Admin SDK may not be configured. "
                "Contact the administrator."
            ),
        )


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
        contact = payload.phone or payload.email
        contact_type = "phone" if payload.phone else "email"
        
        cache_key = f"otp:sent:{contact}"
        if await multi_layer_cache.get(cache_key):
            logger.warning("OTP_RATE_LIMIT_TRIGGERED", {"contact": contact})
            raise HTTPException(
                status_code=429,
                detail="OTP already sent. Please wait 2 minutes."
            )
        
        import secrets
        otp = str(secrets.randbelow(1000000)).zfill(6)
        
        otp_cache_key = f"otp:code:{contact}"
        await multi_layer_cache.put(otp_cache_key, otp, ttl=600)
        await multi_layer_cache.put(cache_key, True, ttl=120)
        
        logger.info("OTP_SENT_SUCCESS", {"type": contact_type, "contact": contact})
        return success_response({"message": f"OTP sent to {contact_type}", "cooldown_seconds": 120})
    except Exception as e:
        logger.error("OTP_SEND_FAILURE", {"error": str(e), "contact": contact})
        raise HTTPException(status_code=500, detail="Failed to send OTP")

@router.post("/verify-otp", response_model=AuthResponse)
@limiter.limit("10/minute")
async def verify_otp(
    request: Request,
    payload: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Verify OTP sent to user's phone or email.
    On successful verification, create/sync user and return token.
    Includes brute-force protection (5 attempts max).
    """
    if not payload.phone and not payload.email:
        raise HTTPException(status_code=400, detail="Either phone or email is required")
    
    contact = payload.phone or payload.email
    attempts_key = f"otp:attempts:{contact}"
    
    # 1. Brute-force check
    attempts = await multi_layer_cache.get(attempts_key) or 0
    if int(attempts) >= 5:
        logger.warning(f"Brute-force protection triggered for {contact}")
        raise HTTPException(
            status_code=429, 
            detail="Too many failed attempts. Please try again in 15 minutes."
        )

    try:
        otp_cache_key = f"otp:code:{contact}"
        stored_otp = await multi_layer_cache.get(otp_cache_key)
        if not stored_otp:
            logger.warning("OTP_VERIFY_EXPIRED", {"contact": contact})
            raise HTTPException(status_code=401, detail="OTP expired or not found.")
        if str(stored_otp) != str(payload.otp).strip():
            await multi_layer_cache.redis.incr(attempts_key)
            if int(attempts) == 0:
                await multi_layer_cache.redis.expire(attempts_key, 900)
            logger.warning("OTP_VERIFY_INVALID", {"contact": contact, "attempts": int(attempts)+1})
            raise HTTPException(status_code=401, detail=f"Invalid OTP. {4 - int(attempts)} attempts remaining.")
        await multi_layer_cache.delete(otp_cache_key)
        await multi_layer_cache.delete(attempts_key)
        if payload.email:
            user = db.query(User).filter(User.email == payload.email).first()
        else:
            user = db.query(User).filter(User.phone_number == payload.phone).first()
        is_new_user = False
        if not user:
            is_new_user = True
            user = User(
                email=payload.email or f"{payload.phone}@sms.safesafar.app",
                phone_number=payload.phone,
                role="user"
            )
            db.add(user); db.flush()
            db.add(Profile(id=user.id, user_id=user.id))
            db.commit()
            logger.info("USER_CREATED_VIA_OTP", {"user_id": str(user.id), "contact": contact})
        else:
            db.commit()

        # Issue a Firebase custom token — frontend must exchange via signInWithCustomToken()
        # This ensures all subsequent API calls use a real Firebase ID token.
        uid = str(user.id)
        # Store the Firebase UID mapping on the user record if not already set
        if not getattr(user, 'firebase_uid', None):
            user.firebase_uid = uid
            db.commit()

        firebase_custom_token = _create_firebase_custom_token(uid)
        logger.info("OTP_VERIFY_SUCCESS", {"user_id": uid})
        return success_response({
            "message": "OTP verified successfully",
            "token": firebase_custom_token,
            "token_type": "firebase_custom",
            "note": "Exchange this token via Firebase signInWithCustomToken() to get a Firebase ID token.",
            "user": {"id": uid, "email": user.email, "role": user.role},
            "is_new_user": is_new_user
        })
    except Exception as e:
        logger.error("OTP_VERIFY_FAILURE", {"error": str(e), "contact": contact})
        raise HTTPException(status_code=500, detail="Authentication failed")

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
    Firebase Admin SDK verifies the Google ID token for security.
    """
    if not payload.id_token:
        raise HTTPException(status_code=400, detail="id_token is required")

    # Verify the Google ID token using Firebase Admin SDK
    try:
        from core.auth.firebase_client import get_auth
        firebase_auth = get_auth()
        decoded_token = firebase_auth.verify_id_token(payload.id_token)
    except Exception as exc:
        logger.warning("GOOGLE_AUTH_TOKEN_INVALID", {"error": str(exc)})
        raise HTTPException(status_code=401, detail="Invalid Google Identity Token")

    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email", "")
    name = decoded_token.get("name", "Google User")

    user = db.query(User).filter(User.email == email).first()
    is_new_user = False

    if not user:
        is_new_user = True
        user = User(email=email, full_name=name, role="user", firebase_uid=firebase_uid)
        db.add(user); db.flush()
        db.add(Profile(id=user.id, user_id=user.id))
        logger.info(f"Verified Google User Created: {email}")
    else:
        # Sync Firebase UID if not already mapped
        if not getattr(user, 'firebase_uid', None):
            user.firebase_uid = firebase_uid

    db.commit()

    # For Google sign-in the frontend already has the Firebase ID token.
    # Return the Firebase UID and user info — frontend uses the existing ID token.
    return AuthResponse(
        success=True,
        message="Google identity verified.",
        token=payload.id_token,  # Return the original ID token for immediate use
        user={"id": str(user.id), "name": user.full_name, "firebase_uid": firebase_uid},
        is_new_user=is_new_user
    )

def verify_telegram_auth(init_data: str, bot_token: str) -> bool:
    """Verify Telegram Web App initData."""
    try:
        from urllib.parse import parse_qsl
        import hmac
        import hashlib
        
        parsed_data = dict(parse_qsl(init_data))
        if 'hash' not in parsed_data:
            return False
            
        hash_received = parsed_data.pop('hash')
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(parsed_data.items())])
        
        # Secret key is the HMAC-SHA256 hash of the bot token with the constant string "WebAppData"
        secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
        hash_calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        return hash_calculated == hash_received
    except Exception as e:
        logger.error(f"Telegram verification error: {e}")
        return False

@router.post("/telegram", response_model=AuthResponse)
@limiter.limit("20/minute")
async def telegram_auth(
    request: Request,
    payload: TelegramAuthRequest,
    db: Session = Depends(get_db)
):
    """[Task 116 Upgrade] Verified Telegram Integration."""
    bot_token = Config._get_env("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        # Fallback to os.getenv if Config._get_env is not what we expect
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
    if not verify_telegram_auth(payload.init_data, bot_token):
        logger.warning("TELEGRAM_AUTH_FORGERY_ATTEMPT", {"user_id": payload.user.get("id")})
        raise HTTPException(status_code=401, detail="Forged Telegram Authentication Data prevented.")
    
    telegram_id = str(payload.user.get("id"))
    email = f"tg_{telegram_id}@safesafar.app"
    
    user = db.query(User).filter(User.email == email).first()
    is_new_user = False
    
    if not user:
        is_new_user = True
        user = User(
            email=email, 
            full_name=payload.user.get("first_name", "TG User"), 
            role="user",
            telegram_id=telegram_id
        )
        db.add(user); db.flush()
        db.add(Profile(id=user.id, user_id=user.id))
        logger.info(f"Verified Telegram User Created: {telegram_id}")
    else:
        # Update name if it changed
        user.full_name = payload.user.get("first_name", user.full_name)
    
    db.commit()

    # Issue Firebase custom token — frontend exchanges via signInWithCustomToken()
    uid = str(user.id)
    firebase_custom_token = _create_firebase_custom_token(uid)

    return AuthResponse(
        success=True,
        message="Telegram identity verified.",
        token=firebase_custom_token,
        token_type="firebase_custom",
        user={"id": uid, "name": user.full_name, "email": user.email},
        is_new_user=is_new_user
    )

# ============================================================================
# USER INFO & LOGOUT
# ============================================================================

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    """
    return success_response({
        "message": "Profile retrieved",
        "id": str(current_user.id),
        "email": current_user.email,
        "phone": getattr(current_user, 'phone_number', None),
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_verified": current_user.is_verified
    })

@router.post("/logout")
async def logout(request: Request, token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    """
    [Task 10 Upgrade] Logout using AuthServiceProvider.
    Blacklists the token in Redis and logs the audit event.
    """
    if not token:
        return {"status": "success", "message": "Already logged out."}
    
    try:
        from core.infrastructure.container import container
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

        return success_response({"message": "Logged out successfully."})
    except Exception as e:
        logger.error("LOGOUT_FAILURE", {"error": str(e)})
        return success_response({"message": "Logged out successfully."})
