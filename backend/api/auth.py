from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.database import get_db
from backend.services.user_service import UserService
from backend.utils.security import create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, credentials_exception
from backend.database.models import User
from backend.api.dependencies import get_current_user
from backend.services.cache_service import cache_service

import uuid
from backend.config import Config

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    is_new_user: Optional[bool] = False

class SendOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    otp: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class TelegramAuthRequest(BaseModel):
    init_data: str
    user: Dict[str, Any] # This should match the structure from telegram auth

class UserProfileUpdate(BaseModel):
    # Define fields for user profile updates
    # Example:
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    # Add other fields as necessary

class UserLocationUpdate(BaseModel):
    latitude: float
    longitude: float

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

@router.post("/send-otp", response_model=AuthResponse)
async def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    # Placeholder for OTP sending logic
    # In a real application, you would integrate with an SMS/email service here
    if not request.phone and not request.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either phone or email must be provided.")
    
    # Simulate OTP generation and sending
    # For demonstration, we'll just return success.
    # In a real scenario, you'd store the OTP and its expiry in the DB/cache
    # and send it to the user.
    print(f"Simulating OTP sent to {request.phone or request.email}")
    return AuthResponse(success=True, message="OTP sent successfully.")

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    # Placeholder for OTP verification logic
    # In a real application, you would compare the provided OTP with the stored one.
    if request.otp == "123456": # Dummy OTP for demonstration
        user_service = UserService(db)
        user = user_service.get_user_by_email(request.email) if request.email else user_service.get_user_by_phone(request.phone)
        is_new_user = False
        if not user:
            # If user doesn't exist, create a new one
            user_data = {"email": request.email} if request.email else {"phone": request.phone}
            user = user_service.create_user_with_data(user_data) # You'll need to implement this in UserService
            is_new_user = True
        
        access_token = create_access_token(data={"sub": user.email if user.email else user.phone}) # Assuming email or phone is unique
        
        # Generate Refresh Token
        refresh_token = str(uuid.uuid4())
        # Store in Redis with TTL from Config
        if cache_service.is_available():
            cache_service.set(
                f"refresh_token:{refresh_token}", 
                user.id, 
                ttl_seconds=Config.JWT_REFRESH_EXPIRATION_DAYS * 86400
            )

        return AuthResponse(
            success=True, 
            message="OTP verified successfully.", 
            token=access_token, 
            refresh_token=refresh_token,
            user=user.to_dict(), 
            is_new_user=is_new_user
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

@router.post("/google", response_model=AuthResponse)
async def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    # Placeholder for Google authentication logic
    # In a real app, verify the id_token with Google's API
    # Example: idinfo = await id_token.verify_oauth2_token(request.id_token, requests.Request(), GOOGLE_CLIENT_ID)
    print(f"Simulating Google auth with token: {request.id_token}")
    
    # Assume token is valid for demonstration
    user_email = "google_user@example.com" # Extract from id_token in real app
    user_service = UserService(db)
    user = user_service.get_user_by_email(user_email)
    is_new_user = False
    if not user:
        user = user_service.create_user_with_data({"email": user_email})
        is_new_user = True
    
    access_token = create_access_token(data={"sub": user.email})
    
    # Generate Refresh Token
    refresh_token = str(uuid.uuid4())
    if cache_service.is_available():
        cache_service.set(
            f"refresh_token:{refresh_token}", 
            user.id, 
            ttl_seconds=Config.JWT_REFRESH_EXPIRATION_DAYS * 86400
        )

    return AuthResponse(
        success=True, 
        message="Google auth successful.", 
        token=access_token, 
        refresh_token=refresh_token,
        user=user.to_dict(), 
        is_new_user=is_new_user
    )

@router.post("/telegram", response_model=AuthResponse)
async def telegram_auth(request: TelegramAuthRequest, db: Session = Depends(get_db)):
    # Placeholder for Telegram authentication logic
    # In a real app, verify init_data using Telegram's recommended method
    print(f"Simulating Telegram auth with init_data: {request.init_data} and user: {request.user}")
    
    telegram_id = request.user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Telegram user ID not found.")

    user_service = UserService(db)
    user = user_service.get_user_by_telegram_id(telegram_id) # You'll need to implement this
    is_new_user = False
    if not user:
        user_data = {"telegram_id": telegram_id, "first_name": request.user.get("first_name"), "last_name": request.user.get("last_name")}
        user = user_service.create_user_with_data(user_data)
        is_new_user = True

    access_token = create_access_token(data={"sub": user.email if user.email else user.telegram_id})
    
    # Generate Refresh Token
    refresh_token = str(uuid.uuid4())
    if cache_service.is_available():
        cache_service.set(
            f"refresh_token:{refresh_token}", 
            user.id, 
            ttl_seconds=Config.JWT_REFRESH_EXPIRATION_DAYS * 86400
        )

    return AuthResponse(
        success=True, 
        message="Telegram auth successful.", 
        token=access_token, 
        refresh_token=refresh_token,
        user=user.to_dict(), 
        is_new_user=is_new_user
    )

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using a valid refresh token.
    """
    if not cache_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service unavailable for token refresh."
        )

    user_id = cache_service.get(f"refresh_token:{request.refresh_token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    user_service = UserService(db)
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Generate new access token
    new_access_token = create_access_token(data={"sub": user.email if user.email else user.phone})
    
    # Optional: Rotate refresh token (highly recommended for security)
    new_refresh_token = str(uuid.uuid4())
    cache_service.delete(f"refresh_token:{request.refresh_token}")
    cache_service.set(
        f"refresh_token:{new_refresh_token}", 
        user.id, 
        ttl_seconds=Config.JWT_REFRESH_EXPIRATION_DAYS * 86400
    )

    return AuthResponse(
        success=True,
        message="Token refreshed successfully.",
        token=new_access_token,
        refresh_token=new_refresh_token,
        user=user.to_dict()
    )

@router.get("/me", response_model=AuthResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return AuthResponse(success=True, message="Current user fetched.", user=current_user.to_dict())

@router.put("/user/profile", response_model=AuthResponse)
async def update_user_profile(profile_update: UserProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_service = UserService(db)
    updated_user = user_service.update_user_profile(current_user, profile_update.dict(exclude_unset=True)) # Implement this in UserService
    return AuthResponse(success=True, message="Profile updated successfully.", user=updated_user.to_dict())

@router.post("/user/location", response_model=AuthResponse)
async def update_user_location(location_update: UserLocationUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_service = UserService(db)
    updated_user = user_service.update_user_location(current_user, location_update.latitude, location_update.longitude) # Implement this
    return AuthResponse(success=True, message="Location updated successfully.", user=updated_user.to_dict())

@router.post("/logout", response_model=AuthResponse)
async def logout(request: LogoutRequest, token: str = Depends(oauth2_scheme)):
    """
    Adds the current user's token to a blacklist to invalidate it.
    Optionally revokes a refresh token sent in the body.
    """
    if cache_service.is_available():
        # blacklist the access token with remaining TTL
        cache_service.set(f"jwt_blacklist:{token}", 1, ttl_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        # revoke refresh token if provided
        if request.refresh_token:
            cache_service.delete(f"refresh_token:{request.refresh_token}")
        return AuthResponse(success=True, message="Logged out successfully.")
    else:
        # If Redis is not available, we can't blacklist.
        # The frontend should still delete the token.
        return AuthResponse(success=True, message="Logged out successfully (no blacklist).")