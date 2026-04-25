from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Profile, Booking
from dependencies import get_current_user
from utils.responses import v3_response, success_response
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
    return v3_response(
        status="ACTIVE",
        data={
            "email": current_user.email,
            "supabase_id": current_user.supabase_id,
            "name": profile.name if profile else None,
            "role": current_user.role,
            "joined_at": current_user.created_at
        }
    )

@router.post("/profile/sync")
async def sync_profile_metadata(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sync metadata (name, avatar) from Supabase to local user_store.db.
    """
    profile = current_user.profile
    if not profile:
        profile = Profile(user_id=current_user.id, id=current_user.supabase_id)
        db.add(profile)
    
    if "name" in data: profile.name = data["name"]
    if "avatar_url" in data: profile.avatar_url = data["avatar_url"]
    
    db.commit()
    logger.info(f"USER_SYNC | Profile synced for {current_user.id}")
    return success_response(message="Profile synced")

@router.get("/history/bookings")
async def get_booking_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch past bookings from the lightweight user_store.db.
    """
    bookings = db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).order_by(Booking.travel_date.desc()).limit(limit).all()
    
    return success_response(
        message=f"Fetched {len(bookings)} bookings",
        data=[{
            "id": b.id,
            "travel_date": b.travel_date,
            "status": b.status,
            "amount": b.amount_paid
        } for b in bookings]
    )

@router.get("/preferences")
async def get_search_preferences(current_user: User = Depends(get_current_user)):
    """
    Fetch search preferences.
    """
    memory = current_user.profile.ai_memory if current_user.profile else {}
    return success_response(
        data=memory.get("search_preferences", {"class": "3A", "quota": "GN"})
    )

@router.get("/active-session")
async def get_active_payment_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent CREATED booking to allow session recovery.
    """
    from database.models import EscrowStatus
    
    active_booking = db.query(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.escrow_status == EscrowStatus.CREATED
    ).order_by(Booking.created_at.desc()).first()
    
    return success_response(
        data={
            "has_active": bool(active_booking),
            "booking_id": active_booking.id if active_booking else None,
            "amount": active_booking.amount_paid if active_booking else 0,
            "vpa": active_booking.merchant_vpa if active_booking else None,
            "created_at": active_booking.created_at if active_booking else None
        }
    )

@router.get("/sessions")
async def get_my_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all active user sessions."""
    from database.models import UserSession
    sessions = db.query(UserSession).filter(
        UserSession.user_id == user.id
    ).order_by(UserSession.login_at.desc()).limit(10).all()
    
    return success_response(
        data=[{
            "id": s.id,
            "login_at": s.login_at,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent
        } for s in sessions]
    )

@router.post("/sessions/{session_id}/revoke")
async def revoke_user_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke a specific session."""
    from database.models import UserSession
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    db.delete(session)
    db.commit()
    
    logger.info(f"USER_SESSION_REVOKE | {session_id} | {user.id}")
    return success_response(message="Session revoked")

@router.delete("/")
async def delete_user_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Systematic user data wipe (GDPR compliance).
    """
    from database.models import UserSession, RouteSearchLog, Profile, Booking, PersistentChatMessage
    
    try:
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.query(RouteSearchLog).filter(RouteSearchLog.user_id == user.id).delete()
        db.query(PersistentChatMessage).filter(PersistentChatMessage.user_id == user.id).delete()
        db.query(Booking).filter(Booking.user_id == user.id).update({Booking.user_id: None})
        db.query(Profile).filter(Profile.user_id == user.id).delete()
        db.delete(user)
        
        db.commit()
        logger.info(f"USER_DELETE | {user.id}")
        return success_response(message="Account and associated data deleted successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"USER_DELETE_FAIL | {user.id} | {e}")
        raise HTTPException(status_code=500, detail="Deletion failed")

@router.post("/password-reset/request")
async def request_password_reset(email: str = Body(..., embed=True)):
    """
    Triggers Supabase password reset email flow.
    """
    from core.auth.supabase_client import supabase
    try:
        supabase.auth.reset_password_for_email(email)
        return success_response(message="If the email exists, a reset link has been sent")
    except Exception as e:
        logger.error(f"PWD_RESET_FAIL | {email} | {e}")
        return success_response(message="If the email exists, a reset link has been sent")
