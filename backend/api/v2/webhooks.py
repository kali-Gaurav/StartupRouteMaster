from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Booking, PaymentSession, EscrowStatus, AuditLog
from services.unlock_service import UnlockService
from pydantic import BaseModel
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Payments & Reconciliation"])

class PaymentWebhook(BaseModel):
    utr_number: str
    amount: float
    session_code: Optional[str] = None # For matching
    booking_id: Optional[str] = None
    status: str = "SUCCESS"

@router.post("/payment-simulate")
async def payment_webhook_handler(payload: PaymentWebhook, db: Session = Depends(get_db)):
    """
    Subtask 43.2 & 43.4: Simulated payment webhook handler.
    Matches UTR/Session and transitions state.
    """
    logger.info(f"Incoming Payment Webhook: {payload}")
    
    # [43.3] Transaction Matching Logic
    # Try by booking_id first
    booking = None
    if payload.booking_id:
        booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
    
    # Try by session_code
    if not booking and payload.session_code:
        pay_session = db.query(PaymentSession).filter(PaymentSession.session_code == payload.session_code).first()
        if pay_session:
            # Find the booking linked to this route/user
            booking = db.query(Booking).filter(
                Booking.user_id == pay_session.user_id,
                Booking.route_id == pay_session.route_id,
                Booking.escrow_status == EscrowStatus.CREATED
            ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="No matching booking found for this payment.")

    # [43.5] Fraud Detection: Check if UTR already used
    existing_utr = db.query(Booking).filter(Booking.utr_number == payload.utr_number).first()
    if existing_utr:
        raise HTTPException(status_code=400, detail="UTR already processed.")

    # [43.4] Automatic State Transition
    booking.utr_number = payload.utr_number
    
    if booking.service_type == "UNLOCK":
        UnlockService.fulfill_unlock(db, booking.id)
    else:
        # For AGENT_BOOKING, mark as VERIFIED
        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "Payment verified by bank webhook. Awaiting agent."
        
        # [43.8] Audit Log
        audit = AuditLog(
            entity_type="Booking",
            entity_id=booking.id,
            action="PAYMENT_VERIFIED_WEBHOOK",
            new_value="VERIFIED",
            performed_by="WEBHOOK_PROVIDER",
            reason=f"Auto-verified via UTR: {payload.utr_number}"
        )
        db.add(audit)
        db.commit()

    return {"status": "accepted", "message": "Payment processed successfully."}
