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
from datetime import datetime, date, timedelta

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
            
            # [Task 43.C] Referral Conversion Trigger
            user = db.query(User).filter(User.id == booking.user_id).first()
            if user and user.referral_status == "INITIATED":
                from services.karma_service import karma_service
                karma_service.process_referral_conversion(db, user.id)
                
            db.commit()
        await ws_manager.broadcast_log(booking_id, "✅ Route Details Unlocked!", "COMPLETED")
        return

    # For AGENT_BOOKING, we wait for the Admin (the user) to process it
    await ws_manager.broadcast_log(booking_id, "📬 Request sent to Admin. Waiting for IRCTC booking...")
    
    # Task 20: Admin Notification (Console & Logic)
    logger.info(f"🚨 ADMIN ALERT: New AGENT_BOOKING ready for processing! ID: {booking_id}")
    
    # [Task 42.D] CREDIT_TOPUP Auto-Fulfillment
    if service_type == "CREDIT_TOPUP":
        from services.credit_service import credit_service
        with SessionLocal() as db:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if booking:
                bundle_id = booking.booking_details.get("bundle_id", "STARTER_5")
                # Add paid credits
                credit_service.top_up_credits(db, booking.user_id, bundle_id, booking.id)
                booking.escrow_status = EscrowStatus.COMPLETED
                booking.escrow_message = f"✅ Credits Added! New Balance available."
                db.commit()
                await ws_manager.broadcast_log(booking_id, "✅ Credits Successfully Added to Pocket!", "COMPLETED")
        return

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
    
    # [Task 45.3] Project Shield: ANTI-SCRAPER HONEYPOT
    if journey_id == "RM_HONEYPOT_BETA_99":
        from services.fraud_service import fraud_service
        # Instantly mark user as HIGH RISK
        fraud_service.create_alert(db, user.id, "SCRAPER_HONEYPOT_TRIGGER", "CRITICAL", {"ip": "AUTOMATED"})
        raise HTTPException(status_code=403, detail="Automated access detected. Your IP is being logged.")

    # 1. Fetch Journey Data (From cache populated by search)
    from services.journey_cache import get_journey
    journey = await get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=400, detail="Journey expired or invalid. Please search again.")

    # [Task 42.C] TOKEN ECONOMY: Check for Credits
    from services.credit_service import credit_service
    balances = credit_service.get_user_balance(db, user.id)
    has_credits = balances["total"] >= 1
    
    # [Task 41.2] Subscription-Aware Pricing
    is_pro = (user.subscription and user.subscription.plan_tier in ["PRO", "ELITE"] 
              and (not user.subscription.expires_at or user.subscription.expires_at > datetime.utcnow()))
    
    # DECISION: Free or Credit or Paid
    use_credit = False
    if is_pro:
        unlock_fee = 0.0
    elif has_credits:
        unlock_fee = 0.0
        use_credit = True
    else:
        unlock_fee = PlatformConfigService.get_fee(db, "UNLOCK_FEE")
        
    agent_fee = PlatformConfigService.get_fee(db, "AGENT_BOOKING_FEE")

    if service_type == "UNLOCK":
        base_fee = unlock_fee
        if is_pro:
            escrow_msg = "Free Reward: Route Unlocked via Pro Subscription."
        else:
            escrow_msg = f"Awaiting payment to UNLOCK route details (Fee: ₹{unlock_fee})."
    else:
        # AGENT_BOOKING logic: Ticket + Unlock + Agent assist
        fare = journey.get("total_fare", 0.0)
        # Pro users don't pay the unlock portion, but they pay for the ticket and agent labor
        base_fee = fare + (0.0 if is_pro else unlock_fee) + agent_fee
        escrow_msg = "Awaiting payment for AGENT-ASSISTED booking."

    # 3. Calculate Final Amount
    from utils.payments import generate_upi_uri, get_unique_paisa_amount
    merchant_info = merchant_vpa_service.get_next_vpa()
    total_amount = get_unique_paisa_amount(base_fee, db, merchant_info["vpa"]) if base_fee > 0 else 0.0

    if total_amount <= 0:
        # [41.2] AUTO-UNLOCK EXEMPTION for PRO Users OR [42.C] Credit Consumption
        msg = "✅ [PRO-EXCLUSIVE] Free Unlock!" if is_pro else "🎟️ Credit Applied!"
        
        # [Task 42.C HARDENING] Deduct Credit BEFORE creating record for non-pro users
        if not is_pro and use_credit:
            from services.credit_service import credit_service
            # Atomic deduction check
            deducted = credit_service.consume_credit(db, user.id, "PENDING")
            if not deducted:
                raise HTTPException(status_code=402, detail="Token deduction failed. Please check your balance.")

        new_booking = Booking(
            id=booking_id_placeholder,
            user_id=user.id,
            service_type=service_type,
            escrow_status=EscrowStatus.COMPLETED,
            escrow_message=msg,
            amount_paid=0.0,
            is_unlocked=True,
            booking_details=journey,
            created_at=datetime.utcnow()
        )
        db.add(new_booking)

        # Update Credit Transaction with real booking_id instead of "PENDING" placeholder
        if not is_pro and use_credit:
             from database.models import CreditTransaction
             last_tx = db.query(CreditTransaction).filter(
                 CreditTransaction.user_id == user.id, 
                 CreditTransaction.reference_entity_id == "PENDING"
             ).order_by(CreditTransaction.timestamp.desc()).first()
             if last_tx: last_tx.reference_entity_id = new_booking.id

        # [Task 43.C] REFERRAL CONVERSION
        if user.referral_status == "INITIATED":
            from services.karma_service import karma_service
            karma_service.process_referral_conversion(db, user.id)

        db.commit()
        return {
            "id": new_booking.id,
            "amount": 0.0,
            "status": "COMPLETED",
            "message": "Route Unlocked via Subscription or Credits!"
        }

    # (Else, continue with UPI generation as before...)
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

@router.post("/{booking_id}/regenerate")
async def regenerate_payment(
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    [22.2] Regenerate QR/VPA for an expired payment session.
    [22.3] Auto-assigns new Merchant VPA.
    """
    from database.models import PaymentSession
    from utils.payments import generate_upi_uri
    
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
        
    if booking.escrow_status != EscrowStatus.CREATED:
        raise HTTPException(status_code=400, detail="Only CREATED bookings can be regenerated.")

    # 1. Select new VPA
    merchant = merchant_vpa_service.get_next_vpa()
    upi_id = merchant["vpa"]
    
    # 2. Update Booking
    booking.merchant_vpa = upi_id
    
    # 3. Create new PaymentSession record
    session_code = f"RM_{uuid.uuid4().hex[:8].upper()}"
    new_session = PaymentSession(
        user_id=user.id,
        booking_id=booking.id,
        session_code=session_code,
        amount=booking.amount_paid,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db.add(new_session)
    
    # 4. Generate Link
    txn_note = f"RM_{booking.id[:8].upper()}"
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=upi_id,
        merchant_name=merchant["name"],
        amount=booking.amount_paid,
        transaction_note=txn_note
    )
    
    db.commit()
    
    return {
        "status": "success",
        "message": "New payment session generated.",
        "upi_url": upi_link,
        "vpa": upi_id,
        "expires_at": new_session.expires_at.isoformat()
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
    """
    # [23.2] Initialize cache for distributed lock
    await multi_layer_cache.initialize()
    
    # [23.3] Distributed Lock using UTR number (Moved to top)
    lock_key = f"lock:utr:{payload.utr_number}"
    if multi_layer_cache.redis:
        acquired = await multi_layer_cache.redis.set(lock_key, "locked", ex=60, nx=True)
        if not acquired:
            logger.warning(f"Lock already held for {lock_key}")
            raise HTTPException(status_code=429, detail="Processing already in progress for this UTR.")

    try:
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

        # [26.3] Centralized State Transition with Validation
        booking.update_escrow_status(
            db, 
            EscrowStatus.UTR_SUBMITTED, 
            message="UTR received. Verifying with bank...",
            performed_by=f"USER_{user.id}",
            reason=f"UTR: {payload.utr_number}"
        )
        db.commit()

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
    except Exception as e:
        # Re-raise to let FastAPI handle
        raise e

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
