from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Profile, Booking
from dependencies import get_current_user

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
