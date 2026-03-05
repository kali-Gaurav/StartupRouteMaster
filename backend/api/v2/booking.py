from fastapi import APIRouter, Depends, HTTPException, Body, Header, Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Booking, QuotaType, BookingStatus, EscrowStatus
from dependencies import get_current_user
from services.multi_layer_cache import multi_layer_cache
from schemas.base import BookingResponseSchema, SubmitUtrSchema
import uuid
import time
from datetime import datetime, date
import asyncio

router = APIRouter(prefix="/booking", tags=["Booking Engine"])

@router.post("/initiate", response_model=BookingResponseSchema)
async def initiate_booking(
    journey_id: str = Body(..., embed=True),
    idempotency_key: str = Header(..., description="Client-generated unique ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Initiates a zero-gateway UPI Escrow booking.
    """
    await multi_layer_cache.initialize()
    
    # --- 1. Idempotency Check ---
    idem_key = f"idem:booking:{idempotency_key}"
    existing_id = await multi_layer_cache.redis.get(idem_key)
    if existing_id:
        existing_booking = db.query(Booking).filter(Booking.id == existing_id.decode()).first()
        if existing_booking:
            return existing_booking

    # --- 2. Inventory Pre-check ---
    from services.journey_cache import get_journey
    journey = await get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=400, detail="Journey expired or invalid. Please re-search.")

    # --- 3. Fare Lock ---
    fare_lock_key = f"fare_lock:{journey_id}"
    locked_fare = await multi_layer_cache.redis.get(fare_lock_key)
    fare_amount = float(locked_fare.decode()) if locked_fare else journey.get("total_fare", 0.0)
    if not locked_fare:
        await multi_layer_cache.redis.setex(fare_lock_key, 600, str(fare_amount))
    
    # --- 4. Generate UPI Details ---
    upi_id = "gauravnagar@okaxis" # Target UPI
    upi_tx_id = f"TX{int(time.time())}{str(uuid.uuid4().hex[:6]).upper()}"
    note = f"Booking_{upi_tx_id}"
    upi_link = f"upi://pay?pa={upi_id}&pn=RouteMaster&am={fare_amount}&cu=INR&tn={note}&tr={upi_tx_id}"

    # --- 5. Create local Booking record (Escrow State: CREATED) ---
    new_booking = Booking(
        user_id=user.id,
        pnr_number=str(uuid.uuid4().hex[:10]).upper(), # Temporary PNR until confirmed
        travel_date=date.fromisoformat(journey["date"].split(' ')[0]),
        booking_status=BookingStatus.PENDING.value,
        escrow_status=EscrowStatus.CREATED,
        amount_paid=fare_amount,
        upi_tx_id=upi_tx_id,
        booking_details=journey,
        trip_id=journey["legs"][0].get("trip_id") if journey.get("legs") else None,
        train_number=journey["legs"][0].get("train_number") if journey.get("legs") else None
    )
    
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    await multi_layer_cache.redis.setex(idem_key, 86400, new_booking.id)
    
    # Inject upi_url for the frontend
    response_data = BookingResponseSchema.model_validate(new_booking).model_dump()
    response_data["upi_url"] = upi_link
    
    return response_data

@router.post("/{booking_id}/utr", response_model=BookingResponseSchema)
async def submit_utr(
    payload: SubmitUtrSchema,
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submits a UTR for manual verification, transitioning the state.
    Includes mock AI verification pipeline.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking.escrow_status != EscrowStatus.CREATED:
        raise HTTPException(status_code=400, detail=f"Booking is already in state: {booking.escrow_status.name}")

    # Update state to UTR_SUBMITTED
    booking.utr_number = payload.utr_number
    booking.escrow_status = EscrowStatus.UTR_SUBMITTED
    db.commit()
    db.refresh(booking)
    
    # Trigger background mock verification
    asyncio.create_task(_mock_verification_pipeline(booking.id))
    
    return booking

async def _mock_verification_pipeline(booking_id: str):
    """Background task to simulate the verification and AI booking process."""
    await asyncio.sleep(2) # Simulate UTR check
    db = next(get_db())
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return
        
        booking.escrow_status = EscrowStatus.VERIFIED
        db.commit()
        
        await asyncio.sleep(2) # Simulate AI logging in
        booking.escrow_status = EscrowStatus.BOOKING_INITIATED
        db.commit()
        
        await asyncio.sleep(3) # Simulate AI Booking and getting PNR
        booking.escrow_status = EscrowStatus.COMPLETED
        booking.booking_status = BookingStatus.CONFIRMED.value
        # Real PNR from IRCTC would go here
        db.commit()
    finally:
        db.close()

@router.get("/{booking_id}/status", response_model=BookingResponseSchema)
async def get_booking_status(
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Polls the current status of the booking/escrow.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking
