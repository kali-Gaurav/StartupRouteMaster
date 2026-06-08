from typing import cast, Dict, Any, List, Optional
from services.platform_config_service import PlatformConfigService
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Body, Header, Path, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session
from database.session import get_db, SessionLocal
from database.models import User, Booking, EscrowStatus, BookingStatus
from api.dependencies import get_current_user
from services.multi_layer_cache import multi_layer_cache
from services.booking_service import BookingService
from services.booking_state_machine import BookingStateMachine
from schemas.booking import BookingResponseSchema, SubmitUtrSchema
from utils.responses import v3_response, success_response
import time
import uuid
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/booking", tags=["booking"])

from services.ws_manager import ws_manager
from services.merchant_vpa_service import merchant_vpa_service


def _status_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _booking_response_data(
    booking: Booking,
    upi_url: str | None = None,
    audit_trail: list[Dict[str, Any]] | None = None,
    valid_next_actions: list[str] | None = None
) -> Dict[str, Any]:
    response = {
        "id": str(booking.id),
        "pnr_number": booking.pnr_number,
        "booking_status": _status_value(booking.booking_status),
        "escrow_status": _status_value(booking.escrow_status),
        "escrow_message": booking.escrow_message,
        "amount_paid": float(booking.amount_paid or 0.0),
        "upi_tx_id": booking.upi_tx_id,
        "utr_number": booking.utr_number,
        "upi_url": upi_url,
        "service_type": booking.service_type,
        "is_unlocked": bool(booking.is_unlocked),
        "train_number": booking.train_number,
        "booking_details": booking.booking_details or {},
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "valid_next_actions": valid_next_actions or [],
        "audit_trail": audit_trail or [],
    }
    if hasattr(booking, "booking_status") and hasattr(booking, "escrow_status"):
        response["current_state"] = {
            "booking_status": _status_value(booking.booking_status),
            "escrow_status": _status_value(booking.escrow_status),
        }
    return response


def _enhanced_booking_response_data(
    booking: Booking,
    db: Session,
    upi_url: str | None = None
) -> Dict[str, Any]:
    booking_service = BookingService(db)
    audit_trail = booking_service.get_audit_trail(booking_id=str(booking.id))
    valid_actions = BookingStateMachine.get_valid_next_actions(booking)
    return _booking_response_data(
        booking,
        upi_url=upi_url,
        audit_trail=audit_trail,
        valid_next_actions=valid_actions,
    )

async def mock_escrow_pipeline(booking_id: str):
    """
    Simulates the backend processing of the escrow pipeline.
    """
    await asyncio.sleep(3)
    await ws_manager.broadcast_log(booking_id, "🔍 UTR detected in bank statement. Matching amount...")
    
    with SessionLocal() as db:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking: return
        
        if booking.merchant_vpa:
            merchant_vpa_service.record_volume(booking.merchant_vpa, booking.amount_paid)

        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "✅ Payment Secured! Funds held in RouteMaster Escrow. Notifying Admin..."
        db.commit()
        service_type = booking.service_type
    
    await asyncio.sleep(1)
    await ws_manager.broadcast_log(booking_id, "✅ Payment Secured!", "VERIFIED")

    if service_type == "UNLOCK":
        await asyncio.sleep(2)
        with SessionLocal() as db:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking: return
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.escrow_message = "✅ Route Details Unlocked!"
            booking.is_unlocked = True
            
            user = db.query(User).filter(User.id == booking.user_id).first()
            if user is not None and getattr(user, "referral_status", None) == "INITIATED":
                from services.karma_service import karma_service
                karma_service.process_referral_conversion(db, cast(str, user.id))
            db.commit()
        await ws_manager.broadcast_log(booking_id, "✅ Route Details Unlocked!", "COMPLETED")
        return

    if service_type == "CREDIT_TOPUP":
        from services.credit_service import credit_service
        with SessionLocal() as db:
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if booking:
                bundle_id = booking.booking_details.get("bundle_id", "STARTER_5")
                credit_service.top_up_credits(db, cast(str, booking.user_id), bundle_id, cast(str, booking.id))
                booking.escrow_status = EscrowStatus.COMPLETED
                booking.escrow_message = f"✅ Credits Added!"
                db.commit()
                await ws_manager.broadcast_log(booking_id, "✅ Credits Successfully Added!", "COMPLETED")
        return

@router.post("/initiate")
async def initiate_service(
    journey_id: str = Body(..., embed=True),
    service_type: str = Body("UNLOCK", embed=True),
    applied_sovereign_credits: float = Body(0.0, embed=True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unified Service Initiation."""
    await multi_layer_cache.initialize()
    
    if journey_id == "RM_HONEYPOT_BETA_99":
        from services.fraud_service import fraud_service
        fraud_service.create_alert(db, cast(str, user.id), "SCRAPER_HONEYPOT_TRIGGER", "CRITICAL", {"ip": "AUTOMATED"})
        raise HTTPException(status_code=403, detail="Automated access detected")

    from services.journey_cache import get_journey
    journey = await get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=400, detail="Journey expired. Please search again.")

    from services.credit_service import credit_service
    balances = credit_service.get_user_balance(db, cast(str, user.id))
    has_credits = balances["total"] >= 1
    
    is_pro = (user.subscription and user.subscription.plan_tier in ["PRO", "ELITE"] 
              and (not user.subscription.expires_at or user.subscription.expires_at > datetime.utcnow()))
    
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
        escrow_msg = "Free Reward: Route Unlocked via Pro Subscription." if is_pro else f"Awaiting payment to UNLOCK route details (Fee: ₹{unlock_fee})."
    else:
        fare = journey.get("total_fare", 0.0)
        base_fee = fare + (0.0 if is_pro else unlock_fee) + agent_fee
        escrow_msg = "Awaiting payment for AGENT-ASSISTED booking."

    from services.sovereign_ledger_service import SovereignLedgerService
    wallet = SovereignLedgerService.get_wallet_summary(db, user.id)
    available_sovereign = wallet.get("bonus_credit_balance", 0.0)
    
    # Cap applied credits to available balance and base_fee
    applied_sovereign_credits = min(applied_sovereign_credits, available_sovereign, base_fee)
    
    from utils.payments import generate_upi_uri, get_unique_paisa_amount
    merchant_info = merchant_vpa_service.get_next_vpa()
    
    final_fee = base_fee - applied_sovereign_credits
    total_amount = get_unique_paisa_amount(final_fee, db, merchant_info["vpa"]) if final_fee > 0 else 0.0

    booking_id_placeholder = str(uuid.uuid4())
    short_id = booking_id_placeholder[:8].upper()

    if total_amount <= 0:
        msg = "✅ [PRO-EXCLUSIVE] Free Unlock!" if is_pro else "🎟️ Credit Applied!"
        if not is_pro and use_credit:
            deducted = credit_service.consume_credit(db, cast(str, user.id), "PENDING")
            if not deducted:
                raise HTTPException(status_code=402, detail="Token deduction failed")

        new_booking = Booking(
            id=booking_id_placeholder,
            pnr_number=f"RM{uuid.uuid4().hex[:6].upper()}",
            user_id=cast(str, user.id),
            service_type=service_type,
            booking_status="pending",
            escrow_status=EscrowStatus.COMPLETED,
            escrow_message=msg,
            amount_paid=0.0,
            is_unlocked=True,
            booking_details=journey,
            created_at=datetime.utcnow()
        )
        db.add(new_booking)
        if not is_pro and use_credit:
             from database.models import CreditTransaction
             last_tx = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id, CreditTransaction.reference_entity_id == "PENDING").order_by(CreditTransaction.timestamp.desc()).first()
             if last_tx: last_tx.reference_entity_id = new_booking.id

        if applied_sovereign_credits > 0:
            SovereignLedgerService.apply_credit_to_booking(
                db=db,
                user_id=cast(str, user.id),
                amount=applied_sovereign_credits,
                booking_id=cast(str, new_booking.id)
            )

        if getattr(user, "referral_status", None) == "INITIATED":
            from services.karma_service import karma_service
            karma_service.process_referral_conversion(db, cast(str, user.id))

        db.commit()
        logger.info(f"BOOKING_FREE | {new_booking.id} | {service_type}")
        return success_response(
            message="Service activated successfully",
            data=_booking_response_data(new_booking)
        )

    merchant = merchant_vpa_service.get_next_vpa()
    upi_id = merchant["vpa"]
    total_amount = get_unique_paisa_amount(final_fee, db, upi_id)
    txn_note = f"RM_{short_id}"
    
    upi_link, upi_tx_id = generate_upi_uri(
        merchant_vpa=upi_id,
        merchant_name=merchant["name"],
        amount=total_amount,
        transaction_note=txn_note
    )

    new_booking = Booking(
        id=booking_id_placeholder,
        pnr_number=f"RM{uuid.uuid4().hex[:6].upper()}",
        user_id=user.id,
        service_type=service_type,
        booking_status="pending",
        escrow_status=EscrowStatus.CREATED,
        escrow_message=escrow_msg,
        amount_paid=total_amount,
        merchant_vpa=upi_id, 
        upi_tx_id=upi_tx_id,
        booking_details=journey,
        is_unlocked=False,
        transaction_history=[{
            "tx_id": upi_tx_id, "amount": total_amount, "vpa": upi_id, "type": "initial_request", "note": txn_note, "timestamp": datetime.utcnow().isoformat()
        }],
    )
    db.add(new_booking)
    
    if applied_sovereign_credits > 0:
        SovereignLedgerService.apply_credit_to_booking(
            db=db,
            user_id=cast(str, user.id),
            amount=applied_sovereign_credits,
            booking_id=cast(str, new_booking.id)
        )
        
    db.commit()
    
    logger.info(f"BOOKING_INIT | {new_booking.id} | {total_amount}")
    return success_response(
        message="Payment initiated",
        data=_booking_response_data(new_booking, upi_url=upi_link)
    )

@router.post("/smart-initiate")
async def smart_initiate_booking(
    route_payload: Dict[str, Any] = Body(...),
    passenger_details: List[Dict[str, Any]] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Intelligent Booking Entry Point."""
    from services.orchestration.booking_orchestrator import BookingOrchestrator
    orchestrator = BookingOrchestrator(db)
    result = await orchestrator.execute_smart_booking(user_id=str(user.id), route_payload=route_payload, passenger_details=passenger_details)
    
    if result["status"] == "FAILED":
        raise HTTPException(status_code=400, detail=result["message"])
        
    return success_response(data=result)

@router.post("/{booking_id}/regenerate")
async def regenerate_payment(
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Regenerate QR/VPA for an expired session."""
    from database.models import PaymentSession
    from utils.payments import generate_upi_uri
    
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking.escrow_status != EscrowStatus.CREATED:
        raise HTTPException(status_code=400, detail="Cannot regenerate this booking status")

    merchant = merchant_vpa_service.get_next_vpa()
    upi_id = merchant["vpa"]
    booking.merchant_vpa = upi_id
    
    session_code = f"RM_{uuid.uuid4().hex[:8].upper()}"
    new_session = PaymentSession(user_id=user.id, booking_id=booking.id, session_code=session_code, amount=booking.amount_paid, expires_at=datetime.utcnow() + timedelta(minutes=15))
    db.add(new_session)
    
    txn_note = f"RM_{booking.id[:8].upper()}"
    upi_link, upi_tx_id = generate_upi_uri(merchant_vpa=upi_id, merchant_name=merchant["name"], amount=booking.amount_paid, transaction_note=txn_note)
    
    db.commit()
    logger.info(f"BOOKING_REGEN | {booking_id} | {upi_id}")
    expires_at_iso = new_session.expires_at.isoformat() if new_session.expires_at else None
    return success_response(
        message="Payment regenerated",
        data={**_booking_response_data(booking, upi_url=upi_link), "vpa": upi_id, "expires_at": expires_at_iso}
    )

@router.get("/{booking_id}")
async def get_booking_status(booking_id: str = Path(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Fetches the current status of a service/booking."""
    booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return success_response(data=_enhanced_booking_response_data(booking, db))

@router.get("/")
async def list_bookings(
    status: Optional[str] = Query(None, description="Filter by booking status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List bookings for the authenticated user."""
    query = db.query(Booking).filter(Booking.user_id == user.id)
    if status:
        query = query.filter(Booking.booking_status == status)

    total = query.count()
    bookings = query.order_by(Booking.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return success_response(
        data={
            "total": total,
            "page": page,
            "limit": limit,
            "bookings": [_enhanced_booking_response_data(b, db) for b in bookings]
        }
    )

@router.get("/pnr/{pnr_number}")
async def get_booking_by_pnr(pnr_number: str, db: Session = Depends(get_db)):
    """Lookup a booking by PNR number."""
    booking = db.query(Booking).filter(Booking.pnr_number == pnr_number).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return success_response(data=_enhanced_booking_response_data(booking, db))

@router.post("/{booking_id}/cancel", response_model=None)
async def cancel_booking(
    booking_id: str = Path(...),
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Cancel a booking and trigger refund/cancellation workflow."""
    booking_service = BookingService(db)
    success = booking_service.cancel_booking(
        booking_id=booking_id,
        reason="User cancellation",
        ip_address=request.client.host if request and request.client else None,
        user_id=str(user.id)
    )
    if not success:
        raise HTTPException(status_code=400, detail="Could not cancel booking.")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found after cancellation")
    return success_response(message="Booking cancelled successfully", data=_enhanced_booking_response_data(booking, db))

@router.post("/{booking_id}/utr")
async def submit_utr(
    request: Request,
    payload: SubmitUtrSchema,
    background_tasks: BackgroundTasks,
    booking_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submits a UTR for verification."""
    await multi_layer_cache.initialize()
    lock_key = f"lock:utr:{payload.utr_number}"
    if not multi_layer_cache.redis: raise HTTPException(status_code=503, detail="Cache backend unavailable")
    
    acquired = await multi_layer_cache.redis.set(lock_key, "locked", ex=60, nx=True)
    if not acquired: raise HTTPException(status_code=429, detail="UTR already in process")

    try:
        from utils.payments import validate_utr
        if not validate_utr(payload.utr_number): raise HTTPException(status_code=400, detail="Invalid UTR format")
        
        booking = db.query(Booking).filter(Booking.id == booking_id, Booking.user_id == user.id).first()
        if not booking: raise HTTPException(status_code=404, detail="Booking not found")

        existing_utr = db.query(Booking).filter(Booking.utr_number == payload.utr_number).first()
        if existing_utr:
            if str(existing_utr.id) == str(booking.id):
                return success_response(message="UTR already submitted", data=_enhanced_booking_response_data(booking, db))
            raise HTTPException(status_code=409, detail="UTR already used")

        setattr(booking, "utr_number", payload.utr_number)
        update_escrow_status = getattr(booking, "update_escrow_status")
        update_escrow_status(db, EscrowStatus.UTR_SUBMITTED, message="UTR received. Verifying...", performed_by=f"USER_{cast(str, user.id)}", reason=f"UTR: {payload.utr_number}")
        db.commit()

        from services.telegram_service import telegram_service
        from database.config import Config
        if Config.TELEGRAM_CHAT_ID:
            asyncio.create_task(telegram_service.send_message(Config.TELEGRAM_CHAT_ID, f"💳 *New UTR Submitted*\nBooking: `{booking.id}`\nUTR: `{payload.utr_number}`\nAmount: ₹{booking.amount_paid}"))

        background_tasks.add_task(mock_escrow_pipeline, cast(str, booking.id))
        logger.info(f"UTR_SUBMIT | {booking_id} | {payload.utr_number}")
        return success_response(message="Verification in progress", data=_enhanced_booking_response_data(booking, db))
    except Exception as e:
        logger.error(f"UTR_SUBMIT_ERR | {booking_id} | {e}")
        raise e

@router.post("/{booking_id}/captcha")
async def submit_captcha(captcha: str = Body(..., embed=True), booking_id: str = Path(...)):
    """Internal helper to receive CAPTCHA."""
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis: raise HTTPException(status_code=503, detail="Cache unavailable")
    await multi_layer_cache.redis.setex(f"captcha:{booking_id}", 300, captcha)
    return success_response(data=None, message="CAPTCHA received")

