from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Profile, Booking
from dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User & Account"])

@router.get("/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user profile and local preferences.
    """
    profile = current_user.profile
    return {
        "email": current_user.email,
        "supabase_id": current_user.supabase_id,
        "name": profile.name if profile else None,
        "role": current_user.role,
        "joined_at": current_user.created_at
    }

@router.post("/profile/sync")
async def sync_profile_metadata(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync metadata (name, avatar) from Supabase to local user_store.db.
    (Upgrade Suggestion #4).
    """
    profile = current_user.profile
    if not profile:
        profile = Profile(user_id=current_user.id, id=current_user.supabase_id)
        db.add(profile)
    
    if "name" in data: profile.name = data["name"]
    if "avatar_url" in data: profile.avatar_url = data["avatar_url"]
    
    db.commit()
    return {"status": "success"}

@router.get("/history/bookings")
async def get_booking_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch past bookings from the lightweight user_store.db.
    (TODO #7)
    """
    bookings = db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).order_by(Booking.travel_date.desc()).limit(limit).all()
    
    return bookings

@router.get("/preferences")
async def get_search_preferences(current_user: User = Depends(get_current_user)):
    """
    Fetch search preferences (e.g., Preferred Class) to pre-fill search UI.
    (Upgrade Suggestion #1).
    """
    # Extracted from profile.ai_memory
    memory = current_user.profile.ai_memory if current_user.profile else {}
    return memory.get("search_preferences", {"class": "3A", "quota": "GN"})

@router.get("/active-session")
async def get_active_payment_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [29.1] Returns the most recent CREATED booking to allow session recovery.
    """
    from database.models import EscrowStatus
    
    active_booking = db.query(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.escrow_status == EscrowStatus.CREATED
    ).order_by(Booking.created_at.desc()).first()
    
    if active_booking:
        return {
            "has_active": True,
            "booking_id": active_booking.id,
            "amount": active_booking.amount_paid,
            "vpa": active_booking.merchant_vpa,
            "service_type": active_booking.service_type,
            "created_at": active_booking.created_at
        }
    return {"has_active": False}

@router.get("/sessions")
async def get_my_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """[35.1] List all active user sessions."""
    from database.models import UserSession
    sessions = db.query(UserSession).filter(
        UserSession.user_id == user.id
    ).order_by(UserSession.login_at.desc()).limit(10).all()
    
    return sessions

@router.post("/sessions/{session_id}/revoke")
async def revoke_user_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """[35.2] Revoke a specific session."""
    from database.models import UserSession
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # In a real JWT blacklist system, we'd add the session token to Redis
    # For now, we'll mark it as inactive in DB (assuming we add the column)
    # Since we only have login_at, let's just delete it for this MVP task
    db.delete(session)
    db.commit()
    
    return {"status": "success", "message": "Session revoked."}

@router.delete("/")
async def delete_user_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [37.1] Systematic user data wipe (GDPR compliance).
    Deletes profile, sessions, logs, and anonymizes bookings.
    """
    from database.models import UserSession, RouteSearchLog, Profile, Booking, PersistentChatMessage
    
    try:
        # 1. Delete transient data
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.query(RouteSearchLog).filter(RouteSearchLog.user_id == user.id).delete()
        db.query(PersistentChatMessage).filter(PersistentChatMessage.user_id == user.id).delete()
        
        # 2. Anonymize sensitive bookings (Keep for financial records but remove user link)
        db.query(Booking).filter(Booking.user_id == user.id).update({Booking.user_id: None})
        
        # 3. Delete Profile and User
        db.query(Profile).filter(Profile.user_id == user.id).delete()
        db.delete(user)
        
        db.commit()
        return {"status": "success", "message": "Account and associated data deleted successfully."}
    except Exception as e:
        db.rollback()
        logger.error(f"Account deletion failed for {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Deletion failed. Please contact support.")

@router.post("/password-reset/request")
async def request_password_reset(email: str = Body(..., embed=True)):
    """
    [40.1] Triggers Supabase password reset email flow.
    """
    from core.auth.supabase_client import supabase
    try:
        # Supabase handles the email sending and deep link
        res = supabase.auth.reset_password_for_email(email)
        return {"status": "success", "message": "If the email exists, a reset link has been sent."}
    except Exception as e:
        logger.error(f"Password reset request failed: {e}")
        # Return success anyway to prevent email enumeration attacks
        return {"status": "success", "message": "If the email exists, a reset link has been sent."}
