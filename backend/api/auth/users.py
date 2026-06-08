from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import asyncio

from database import get_db
from database.models import User, Profile
from api.dependencies import get_current_user
from schemas import UserRead
from utils.responses import v3_response, success_response

router = APIRouter(prefix="/user", tags=["users"])


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    emergency_contact: Optional[str] = None


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current logged in user details.
    """
    # Use phone_number instead of phone
    return success_response(
        message="User profile retrieved",
        data={
            "id": str(current_user.id),
            "email": current_user.email,
            "phone": getattr(current_user, "phone_number", None),
            "full_name": current_user.full_name,
            "role": current_user.role,
            "is_verified": current_user.is_verified
        }
    )


@router.patch("/profile")
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the user's profile information.
    """
    def _update():
        profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
        if not profile:
            profile = Profile(user_id=current_user.id, id=current_user.firebase_uid)
            db.add(profile)
        update_data = payload.dict(exclude_unset=True)
        # Only update fields that exist on the Profile model
        for key, value in update_data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        db.commit()
        return profile

    updated_profile = await asyncio.to_thread(_update)
    # Use robust fallback for missing fields
    return success_response(
        message="Profile updated successfully",
        data={
            "name": getattr(updated_profile, "name", None),
            "phone": getattr(updated_profile, "phone", None),
            "gender": getattr(updated_profile, "gender", None),
            "emergency_contact": None  # Not present in Profile, could be fetched from EmergencyContact if needed
        }
    )


@router.post("/location")
async def update_location(
    latitude: float,
    longitude: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the user's current GPS location and check for journey safety.
    """
    from services.user_service import UserService
    from services.emergency.safety_service import safety_service
    
    user_service = UserService(db)
    # 1. Update persistent location history
    await asyncio.to_thread(user_service.update_user_location, current_user, latitude, longitude)
    
    # 2. Safety Check: Journey Deviation
    safety_data = await safety_service.check_journey_deviation(current_user.id, latitude, longitude, db)
    
    return success_response(
        message="Location updated",
        data={
            "latitude": latitude,
            "longitude": longitude,
            "safety": safety_data
        }
    )
