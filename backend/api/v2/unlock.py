from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from database.session import get_db
from services.unlock_service import UnlockService
from typing import Optional, Dict
from datetime import datetime

router = APIRouter(prefix="/unlock", tags=["Monetization & Payments"])

@router.post("/initiate")
async def initiate_unlock(
    request: Request,
    journey_id: str = Query(...),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Subtask 41.8: Initiate the unlock flow.
    [26.2] Automatically reserve seat for 15 mins.
    """
    try:
        # 1. Create the unlock request
        booking = UnlockService.create_unlock_request(db, user_id, journey_id)
        
        # [26.2] Automated Seat Lock (Assume simple mapping for UNLOCK simulation)
        # In production, we'd extract trip_id/coach from journey_id metadata
        from services.inventory_service import InventoryService
        from database.session import SessionTransit
        
        # We use a separate transit session for inventory
        db_transit = SessionTransit()
        try:
            # Mocking trip details from journey_id for this step
            # Real flow would parse the journey structure
            lock_success = InventoryService.reserve_seat_temporary(
                db_transit, trip_id=12625, travel_date=datetime.utcnow().date(), 
                coach_type="SL", booking_id=booking.id
            )
            if not lock_success:
                logger.warning(f"Seat lock failed for booking {booking.id}. Proceeding with caution.")
        finally:
            db_transit.close()
        
        return {
            "status": "success",
            "message": "Unlock request created.",
            "data": {
                "booking_id": booking.id,
                "amount": booking.amount_paid,
                "service_type": booking.service_type,
                "is_unlocked": booking.is_unlocked
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{booking_id}")
async def get_unlock_status(booking_id: str, db: Session = Depends(get_db)):
    """Check if the unlock payment was successful."""
    from database.models import Booking
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    return {
        "booking_id": booking.id,
        "is_unlocked": booking.is_unlocked,
        "escrow_status": booking.escrow_status.value
    }
