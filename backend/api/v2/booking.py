from fastapi import APIRouter, Depends, HTTPException, Body, Header
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Booking, QuotaType, BookingStatus
from dependencies import get_current_user
from services.multi_layer_cache import multi_layer_cache
import uuid
from datetime import datetime, date

router = APIRouter(prefix="/booking", tags=["Booking Engine"])

@router.post("/initiate")
async def initiate_booking(
    journey_id: str = Body(..., embed=True),
    idempotency_key: str = Header(..., description="Client-generated unique ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Initiates a booking request with:
    1. Idempotency Check (Suggestion #1)
    2. Inventory Pre-check (Suggestion #2)
    3. Fare Locking (Suggestion #4)
    """
    await multi_layer_cache.initialize()
    
    # --- 1. Idempotency Check ---
    idem_key = f"idem:booking:{idempotency_key}"
    existing_id = await multi_layer_cache.redis.get(idem_key)
    if existing_id:
        return {"status": "already_processed", "booking_id": existing_id.decode()}

    # --- 2. Inventory Pre-check ---
    # Fetch journey from cache (rt_...)
    from services.journey_cache import get_journey
    journey = await get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=400, detail="Journey expired or invalid. Please re-search.")

    # --- 3. Fare Lock ---
    # Ensure fare hasn't changed drastically or lock it for 10 mins
    fare_lock_key = f"fare_lock:{journey_id}"
    locked_fare = await multi_layer_cache.redis.get(fare_lock_key)
    if not locked_fare:
        # Lock current fare
        await multi_layer_cache.redis.setex(fare_lock_key, 600, str(journey["total_fare"]))
    
    # --- 4. Create local Booking record (Logical Link) ---
    new_booking = Booking(
        user_id=user.id,
        pnr_number=str(uuid.uuid4().hex[:10]).upper(),
        travel_date=date.fromisoformat(journey["date"].split(' ')[0]),
        booking_status="pending",
        amount_paid=0.0, # Not paid yet
        booking_details=journey,
        trip_id=journey["legs"][0].get("trip_id") # Logical ID link
    )
    
    db.add(new_booking)
    db.commit()
    
    # Store ID in idempotency cache
    await multi_layer_cache.redis.setex(idem_key, 86400, new_booking.id)
    
    return {
        "status": "initiated",
        "booking_id": new_booking.id,
        "pnr": new_booking.pnr_number,
        "fare_locked": journey["total_fare"],
        "expires_in": "600s"
    }
