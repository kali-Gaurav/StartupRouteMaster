from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from database.session import get_db
from services.unlock_service import UnlockService
from typing import Optional, Dict

router = APIRouter(prefix="/unlock", tags=["Monetization & Payments"])

@router.post("/initiate")
async def initiate_unlock(
    request: Request,
    journey_id: str = Query(...),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Subtask 41.8: Initiate the unlock flow for a specific journey.
    Returns a pending booking ID to be linked with a payment.
    """
    try:
        # 1. Create the unlock request
        booking = UnlockService.create_unlock_request(db, user_id, journey_id)
        
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
