from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Booking, PaymentSession, EscrowStatus, AuditLog
from services.unlock_service import UnlockService
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Payments & Reconciliation"])

class PaymentWebhook(BaseModel):
    utr_number: str
    amount: float
    session_code: Optional[str] = None # For matching
    booking_id: Optional[str] = None
    status: str = "SUCCESS"

from datetime import datetime
import re

class BankSMSPayload(BaseModel):
    sender: str
    text: str
    received_at: Optional[datetime] = None

def parse_bank_sms(text: str) -> Optional[Dict[str, Any]]:
    """
    [12.3] Regex-parse common Bank SMS templates for UTR and Amount.
    Examples: 
    - "Amt: 49.00 sent to RM... UTR: 123456789012"
    - "Your a/c ..123 debited for Rs 1510.56. Ref: 999988887777"
    """
    # 1. Match 12-digit UTR
    utr_match = re.search(r'\b(\d{12})\b', text)
    # 2. Match Amount (Rs or Amt)
    amt_match = re.search(r'(?:Rs|Amt|INR)\.?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    
    if utr_match:
        utr = utr_match.group(1)
        amt = float(amt_match.group(1).replace(',', '')) if amt_match else 0.0
        return {"utr": utr, "amount": amt}
    return None

@router.post("/bank-sms")
async def bank_sms_webhook(payload: BankSMSPayload, db: Session = Depends(get_db)):
    """
    [12.2] Bank SMS Listener.
    Auto-verifies bookings if UTR matches.
    """
    parsed = parse_bank_sms(payload.text)
    if not parsed:
        logger.warning(f"Failed to parse SMS: {payload.text}")
        return {"status": "ignored", "reason": "No UTR found"}
        
    utr = parsed["utr"]
    amount = parsed["amount"]
    
    # [12.4] Transaction Matching
    booking = db.query(Booking).filter(Booking.utr_number == utr).first()
    
    if booking:
        # [12.5] Auto-verification
        if booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
            booking.escrow_status = EscrowStatus.VERIFIED
            booking.escrow_message = "Auto-verified via Bank SMS."
            
            audit = AuditLog(
                entity_type="Booking",
                entity_id=booking.id,
                action="AUTO_VERIFY_SMS",
                old_value="UTR_SUBMITTED",
                new_value="VERIFIED",
                performed_by="SYSTEM_SMS_BOT",
                reason=f"Parsed UTR {utr} and Amount {amount} from SMS."
            )
            db.add(audit)
            db.commit()
            return {"status": "verified", "booking_id": booking.id}
            
    return {"status": "accepted", "utr": utr, "amount": amount, "matched": bool(booking)}

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
