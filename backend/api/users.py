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
    return success_response(
        message="User profile retrieved",
        data={
            "id": str(current_user.id),
            "email": current_user.email,
            "phone": current_user.phone,
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
            profile = Profile(user_id=current_user.id, id=current_user.supabase_id)
            db.add(profile)
            
        update_data = payload.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)
            
        db.commit()
        return profile
    
    updated_profile = await asyncio.to_thread(_update)
    return success_response(
        message="Profile updated successfully",
        data={
            "name": updated_profile.name,
            "phone": updated_profile.phone,
            "gender": updated_profile.gender,
            "emergency_contact": updated_profile.emergency_contact
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
