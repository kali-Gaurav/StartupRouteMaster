from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import asyncio

from database import get_db
from database.models import User, Profile
from api.dependencies import get_current_user
from schemas import UserRead

router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    emergency_contact: Optional[str] = None


@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get current logged in user details (Auth provided by Supabase JWT).
    """
    return current_user


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
        profile = db.query(Profile).filter(Profile.id == current_user.supabase_id).first()
        if not profile:
            profile = Profile(id=current_user.supabase_id)
            db.add(profile)
            
        update_data = payload.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)
            
        db.commit()
        return profile
    
    if not current_user.supabase_id:
        raise HTTPException(status_code=400, detail="User has no Supabase ID, cannot update profile.")

    updated_profile = await asyncio.to_thread(_update)
    return {"status": "success", "profile": {
        "name": updated_profile.name,
        "phone": updated_profile.phone,
        "gender": updated_profile.gender,
        "emergency_contact": updated_profile.emergency_contact
    }}


@router.post("/location")
async def update_location(
    latitude: float,
    longitude: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the user's current GPS location.
    """
    from services.user_service import UserService
    user_service = UserService(db)
    await asyncio.to_thread(user_service.update_user_location, current_user, latitude, longitude)
    return {"status": "success", "message": "Location updated"}
