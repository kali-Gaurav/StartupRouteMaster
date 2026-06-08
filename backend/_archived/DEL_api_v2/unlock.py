from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from database.session import get_db
from services.unlock_service import UnlockService
from typing import Optional, Dict
from datetime import datetime
import logging
from utils.responses import v3_response, success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/unlock", tags=["Monetization & Payments"])

@router.post("/initiate")
async def initiate_unlock(
    request: Request,
    journey_id: str = Query(...),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Initiate the unlock flow with automated seat lock.
    """
    try:
        booking = UnlockService.create_unlock_request(db, user_id, journey_id)
        
        # Automated Seat Lock
        from services.inventory.service import InventoryService
        from database.session import SessionTransit
        
        db_transit = SessionTransit()
        try:
            # Mocking trip details for simulation
            lock_success = InventoryService.reserve_seat_temporary(
                db_transit, trip_id=12625, travel_date=datetime.utcnow().date(), 
                coach_type="SL", booking_id=str(booking.id))
            
            if not lock_success:
                logger.warning(f"UNLOCK_LOCK_FAIL | Booking: {booking.id}")
        finally:
            db_transit.close()
        
        logger.info(f"UNLOCK_INIT | User: {user_id} | Journey: {journey_id} | Booking: {booking.id}")
        return success_response(
            message="Unlock request initiated",
            data={
                "booking_id": booking.id,
                "amount": booking.amount_paid,
                "service_type": booking.service_type,
                "is_unlocked": booking.is_unlocked
            }
        )
    except Exception as e:
        logger.error(f"UNLOCK_INIT_ERR | {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate unlock")

@router.get("/status/{booking_id}")
async def get_unlock_status(booking_id: str, db: Session = Depends(get_db)):
    """Check if the unlock payment was successful."""
    from database.models import Booking
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    return success_response(
        data={
            "booking_id": booking.id,
            "is_unlocked": booking.is_unlocked,
            "escrow_status": booking.escrow_status.value
        }
    )
