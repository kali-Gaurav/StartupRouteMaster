from fastapi import APIRouter, Depends, HTTPException, Body, Header, Path, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, Booking, EscrowStatus, BookingStatus
from api.dependencies import get_current_user
from services.multi_layer_cache import multi_layer_cache
from schemas.booking import BookingResponseSchema, SubmitUtrSchema
import time
import uuid
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booking", tags=["booking"])

@router.post("/initiate")
async def initiate_service(
    journey_id: str = Body(..., embed=True),
    service_type: str = Body("UNLOCK", embed=True), # UNLOCK or AGENT_BOOKING
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unified Service Initiation.
    - UNLOCK: User pays ₹49 to see full route details.
    - AGENT_BOOKING: User pays Fare + Service Fee for human assistance.
    """
    await multi_layer_cache.initialize()
    
    # 1. Fetch Journey Data (From cache populated by search)
    from services.journey_cache import get_journey
    journey = await get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=400, detail="Journey expired or invalid. Please search again.")

    # 2. Determine Amount
    if service_type == "UNLOCK":
        total_amount = 49.00
        escrow_msg = "Awaiting payment to UNLOCK route details."
    else:
        # AGENT_BOOKING logic
        fare = journey.get("total_fare", 0.0)
        service_fee = 99.00 
        total_amount = fare + service_fee
        escrow_msg = "Awaiting payment for AGENT-ASSISTED booking."

    # 3. Generate UPI URI
    from utils.payments import generate_upi_uri
    merchants = ["anthonynagar1122-1@oksbi", "8529841981@ptsbi"]
    upi_id = merchants[int(time.time() // 60) % len(merchants)]
    
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=upi_id,
        merchant_name="RouteMaster",
        amount=total_amount,
        transaction_note=f"{service_type} RouteMaster"
    )

    # 4. Create Booking Record
    new_booking = Booking(
        user_id=user.id,
        service_type=service_type,
        escrow_status=EscrowStatus.CREATED,
        escrow_message=escrow_msg,
        amount_paid=total_amount,
        upi_tx_id=upi_tx_id,
        booking_details=journey,
        is_unlocked=False,
        transaction_history=[{
            "tx_id": upi_tx_id,
            "amount": total_amount,
            "vpa": upi_id,
            "type": "initial_request",
            "timestamp": datetime.utcnow().isoformat()
        }],
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    return {
        "id": new_booking.id,
        "amount": total_amount,
        "upi_url": upi_link,
        "status": "CREATED",
        "service_type": service_type
    }

@router.get("/{booking_id}", response_model=BookingResponseSchema)
async def get_booking_status(
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Fetches the current status of a service/booking.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@router.post("/{booking_id}/utr")
async def submit_utr(
    request: Request,
    payload: SubmitUtrSchema,
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submits a UTR for verification.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.utr_number = payload.utr_number
    booking.escrow_status = EscrowStatus.UTR_SUBMITTED
    booking.escrow_message = "UTR received. Verifying with bank..."
    db.commit()
    
    # In PROD, this would wait for the Bank SMS Webhook (Task 2)
    # For now, we mock success after 5 seconds
    return {"status": "UTR_SUBMITTED", "message": "Verification in progress."}

@router.post("/{booking_id}/captcha")
async def submit_captcha(
    captcha: str = Body(..., embed=True),
    booking_id: str = Path(...)
):
    """
    Used only for AGENT_BOOKING or internal helpers.
    """
    await multi_layer_cache.initialize()
    redis_key = f"captcha:{booking_id}"
    await multi_layer_cache.redis.setex(redis_key, 300, captcha)
    return {"message": "CAPTCHA received"}
