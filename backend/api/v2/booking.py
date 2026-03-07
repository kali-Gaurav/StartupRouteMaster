import asyncio
from fastapi import APIRouter, Depends, HTTPException, Body, Header, Path, Request, BackgroundTasks
from sqlalchemy.orm import Session
from database.session import get_db, SessionLocal
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

from services.ws_manager import ws_manager

from services.merchant_vpa_service import merchant_vpa_service

async def mock_escrow_pipeline(booking_id: str):
    """
    Simulates the backend processing of the escrow pipeline for payment and booking.
    Transitions: UTR_SUBMITTED -> VERIFIED -> (If AGENT_BOOKING, stop for Admin) -> BOOKING_INITIATED -> COMPLETED
    """
    await asyncio.sleep(3)
    await ws_manager.broadcast_log(booking_id, "🔍 UTR detected in bank statement. Matching amount...")
    
    with SessionLocal() as db:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return
        
        # Task 1.4: Record Volume for VPA
        if booking.merchant_vpa:
            merchant_vpa_service.record_volume(booking.merchant_vpa, booking.amount_paid)

        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "✅ Payment Secured! Funds held in RouteMaster Escrow. Notifying Admin for booking..."
        db.commit()
        service_type = booking.service_type
    
    await asyncio.sleep(1)
    await ws_manager.broadcast_log(booking_id, "✅ Payment Secured! Funds held in RouteMaster Escrow.", "VERIFIED")

    # If it's just an UNLOCK service, we can auto-complete it since there's no IRCTC booking needed
    if service_type == "UNLOCK":
        await asyncio.sleep(2)
        with SessionLocal() as db:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking: return
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.escrow_message = "✅ Route Details Unlocked! Check your dashboard."
            booking.is_unlocked = True
            db.commit()
        await ws_manager.broadcast_log(booking_id, "✅ Route Details Unlocked!", "COMPLETED")
        return

    # For AGENT_BOOKING, we wait for the Admin (the user) to process it
    await ws_manager.broadcast_log(booking_id, "📬 Request sent to Admin. Waiting for IRCTC booking...")
    
    # Task 20: Admin Notification (Console & Logic)
    logger.info(f"🚨 ADMIN ALERT: New AGENT_BOOKING ready for processing! ID: {booking_id}")
    print(f"\n{'='*50}\n🚨 NEW BOOKING REQUEST\nBooking ID: {booking_id}\nAction: Please process via Admin API /docs\n{'='*50}\n")

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
        base_fee = 49.00
        escrow_msg = "Awaiting payment to UNLOCK route details."
    else:
        # AGENT_BOOKING logic: Ticket + 49 (Unlock) + 19 (Agent) = Ticket + 68
        fare = journey.get("total_fare", 0.0)
        base_fee = fare + 68.00
        escrow_msg = "Awaiting payment for AGENT-ASSISTED booking."

    # 3. Generate UPI URI
    from utils.payments import generate_upi_uri, get_unique_paisa_amount
    merchant = merchant_vpa_service.get_next_vpa()
    upi_id = merchant["vpa"]
    
    # Task 2: Cent-matching unique amount
    total_amount = get_unique_paisa_amount(base_fee, db, upi_id)
    
    # Task 4: Transaction Note Serialization (RM_<ShortID>)
    booking_id_placeholder = str(uuid.uuid4())
    short_id = booking_id_placeholder[:8].upper()
    txn_note = f"RM_{short_id}"
    
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=upi_id,
        merchant_name=merchant["name"],
        amount=total_amount,
        transaction_note=txn_note
    )

    # 4. Create Booking Record
    new_booking = Booking(
        id=booking_id_placeholder,
        user_id=user.id,
        service_type=service_type,
        escrow_status=EscrowStatus.CREATED,
        escrow_message=escrow_msg,
        amount_paid=total_amount,
        merchant_vpa=upi_id, 
        upi_tx_id=upi_tx_id,
        booking_details=journey,
        is_unlocked=False,
        transaction_history=[{
            "tx_id": upi_tx_id,
            "amount": total_amount,
            "vpa": upi_id,
            "type": "initial_request",
            "note": txn_note,
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
    background_tasks: BackgroundTasks,
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submits a UTR for verification.
    Task 9: UTR Length & Format Validation
    Task 10: Duplicate UTR Prevention
    """
    from utils.payments import validate_utr
    
    if not validate_utr(payload.utr_number):
        raise HTTPException(status_code=400, detail="Invalid UTR format. Must be 12 digits.")

    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Task 10: Duplicate UTR Prevention
    existing_utr = db.query(Booking).filter(Booking.utr_number == payload.utr_number).first()
    if existing_utr:
        if existing_utr.id == booking.id:
            return {"status": "UTR_SUBMITTED", "message": "UTR already submitted for this booking."}
        raise HTTPException(status_code=409, detail="This UTR has already been used.")

    old_status = booking.escrow_status.value if hasattr(booking.escrow_status, 'value') else str(booking.escrow_status)
    booking.utr_number = payload.utr_number
    booking.escrow_status = EscrowStatus.UTR_SUBMITTED
    booking.escrow_message = "UTR received. Verifying with bank..."
    db.commit()
    
    # Task 17: Audit Log
    from services.audit_service import log_audit
    log_audit(db, "Booking", booking.id, "UTR_SUBMISSION", old_value=old_status, new_value="UTR_SUBMITTED", performed_by=f"USER_{user.id}", reason=f"UTR: {payload.utr_number}")

    # Task 20: Admin Notification (Telegram)
    from services.telegram_service import telegram_service
    from database.config import Config
    if Config.TELEGRAM_CHAT_ID:
        asyncio.create_task(telegram_service.send_message(
            Config.TELEGRAM_CHAT_ID,
            f"💳 *New UTR Submitted*\n\n"
            f"Booking ID: `{booking.id}`\n"
            f"UTR: `{payload.utr_number}`\n"
            f"Amount: ₹{booking.amount_paid}\n"
            f"User: {user.email or user.phone_number}\n\n"
            f"Please verify in bank app."
        ))

    # Trigger background mock processing
    background_tasks.add_task(mock_escrow_pipeline, booking.id)

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
