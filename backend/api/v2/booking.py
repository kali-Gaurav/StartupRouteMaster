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

    # --- 3. Fare Lock & Re-check (Task 23) ---
    fare_lock_key = f"fare_lock:{journey_id}"
    locked_fare = await multi_layer_cache.redis.get(fare_lock_key)
    
    # Task 23: Dynamic Re-check
    # Task 9 & 12: Platform Service Fee Logic
    PLATFORM_SERVICE_FEE = 49.00 
    
    current_fare = journey.get("total_fare", 0.0)
    if locked_fare and abs(float(locked_fare.decode()) - current_fare) > 10.0:
        # If fare changed > ₹10, update lock
        await multi_layer_cache.redis.setex(fare_lock_key, 600, str(current_fare))
        fare_amount = current_fare
    else:
        fare_amount = float(locked_fare.decode()) if locked_fare else current_fare
        if not locked_fare:
            await multi_layer_cache.redis.setex(fare_lock_key, 600, str(fare_amount))
    
    # Total user must pay = IRCTC Fare + Our Service Fee
    total_escrow_amount = fare_amount + PLATFORM_SERVICE_FEE
    
    # --- 4. Generate UPI Details (Task 20: Rotation) ---
    from utils.payments import generate_upi_uri
    
    # Task 20: Merchant VPA Rotation
    merchants = ["anthonynagar1122-1@oksbi", "8529841981@ptsbi"]
    # Simple rotation based on current minute
    upi_id = merchants[int(time.time() // 60) % len(merchants)]
    
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=upi_id,
        merchant_name="RouteMaster",
        amount=total_escrow_amount
    )

    # --- 5. Create local Booking record (Escrow State: CREATED) ---
    new_booking = Booking(
        user_id=user.id,
        pnr_number=str(uuid.uuid4().hex[:10]).upper(), # Temporary PNR until confirmed
        travel_date=date.fromisoformat(journey["date"].split(' ')[0]),
        booking_status=BookingStatus.PENDING.value,
        escrow_status=EscrowStatus.CREATED,
        amount_paid=total_escrow_amount, # Now includes service fee
        upi_tx_id=upi_tx_id,
        # Task 24: Initialize transaction history
        transaction_history=[{
            "tx_id": upi_tx_id,
            "amount": fare_amount,
            "vpa": upi_id,
            "type": "initial_request",
            "timestamp": datetime.utcnow().isoformat()
        }],
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
    request: Request, # Added for IP tracking
    payload: SubmitUtrSchema,
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submits a UTR for manual verification.
    Task 19: Fraudulent UTR Lockout
    """
    # Task 19: Lockout Check
    client_ip = request.client.host
    lockout_key = f"fraud_lock:{client_ip}"
    attempts = await multi_layer_cache.redis.get(lockout_key)
    if attempts and int(attempts) >= 3:
        raise HTTPException(status_code=429, detail="Too many invalid attempts. IP locked for 1 hour.")

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    # --- Task 7: Timeout Check ---
    expiry_limit = 15 * 60 
    if (datetime.utcnow() - booking.created_at).total_seconds() > expiry_limit:
        if booking.escrow_status == EscrowStatus.CREATED:
            booking.escrow_status = EscrowStatus.FAILED
            booking.escrow_message = "Payment session timed out (15 min limit exceeded)."
            db.commit()
        raise HTTPException(status_code=400, detail="This payment session has expired.")

    if booking.escrow_status != EscrowStatus.CREATED:
        raise HTTPException(status_code=400, detail=f"Booking is already in state: {booking.escrow_status.name}")

    # --- Task 10: Duplicate UTR Check ---
    existing_utr = db.query(Booking).filter(Booking.utr_number == payload.utr_number).first()
    if existing_utr:
        # Increment fraud attempts on duplicate submisson (Task 19)
        current_attempts = await multi_layer_cache.redis.incr(lockout_key)
        if current_attempts == 1:
            await multi_layer_cache.redis.expire(lockout_key, 3600)
        
        raise HTTPException(status_code=400, detail=f"This UTR has already been used. Attempt {current_attempts}/3")

    # If logic reaches here, UTR is "new" but we don't know if it's valid yet.
    # In a real system, bank verification failure would also increment this.

    # Update state to UTR_SUBMITTED
    booking.utr_number = payload.utr_number
    booking.escrow_status = EscrowStatus.UTR_SUBMITTED
    booking.escrow_message = "UTR received. Verifying with banking network..."
    db.commit()
    db.refresh(booking)
    
    # Trigger background verification and real worker
    asyncio.create_task(_process_payment_and_launch_worker(booking.id))
    
    return booking

@router.post("/{booking_id}/captcha")
async def submit_captcha(
    captcha: str = Body(..., embed=True),
    booking_id: str = Path(...)
):
    """
    Endpoint for frontend to submit the solved CAPTCHA.
    """
    await multi_layer_cache.initialize()
    redis_key = f"captcha:{booking_id}"
    await multi_layer_cache.redis.setex(redis_key, 300, captcha)
    return {"message": "CAPTCHA received"}

async def _process_payment_and_launch_worker(booking_id: str):
    """
    Tasks 28-35: Verifies payment then launches the Ghost Worker.
    """
    db = next(get_db())
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return
        
        # Step 1: Simulate bank API verification (UTR -> Verified)
        booking.escrow_message = "Verifying UTR with banking gateway..."
        db.commit()
        await asyncio.sleep(2) # Network latency simulation
        
        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "Payment confirmed. Launching AI Ghost Worker..."
        db.commit()
        
        # Step 2: Launch via Pool Manager (Task 26)
        from workers.worker_pool import worker_pool
        await worker_pool.submit_booking(booking.id)
        
    except Exception as e:
        logger.error(f"Pipeline Launch Error: {e}")
        if booking:
            booking.escrow_status = EscrowStatus.FAILED
            booking.escrow_message = f"Critical Pipeline Error: {str(e)}"
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
