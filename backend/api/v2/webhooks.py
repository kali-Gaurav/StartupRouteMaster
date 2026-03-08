from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Booking, PaymentSession, EscrowStatus, AuditLog, BankTransaction
from services.unlock_service import UnlockService
from utils.security import signature_guard # [30.3]
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Payments & Reconciliation"])

# [28.1] Trusted Provider IPs
TRUSTED_WEBHOOK_IPS = {"127.0.0.1", "::1"} # Localhost for dev

def verify_ip(request: Request):
    """[28.2] Strict IP Source Validation."""
    client_ip = request.headers.get("x-forwarded-for") or request.client.host
    if "," in client_ip: client_ip = client_ip.split(",")[0].strip()
    
    if client_ip not in TRUSTED_WEBHOOK_IPS:
        logger.warning(f"Unauthorized Webhook Attempt from IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Unauthorized source IP.")
    return client_ip

class PaymentWebhook(BaseModel):
    utr_number: str
    amount: float
    event_id: Optional[str] = None # [21.1] For Idempotency
    session_code: Optional[str] = None 
    booking_id: Optional[str] = None
    status: str = "SUCCESS"

class BankSMSPayload(BaseModel):
    sender: str
    text: str
    received_at: Optional[datetime] = None

def parse_bank_sms(text: str) -> Optional[Dict[str, Any]]:
    """[12.3] Regex-parse common Bank SMS templates for UTR and Amount."""
    utr_match = re.search(r'\b(\d{12})\b', text)
    amt_match = re.search(r'(?:Rs|Amt|INR)\.?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if utr_match:
        utr = utr_match.group(1)
        amt = float(amt_match.group(1).replace(',', '')) if amt_match else 0.0
        return {"utr": utr, "amount": amt}
    return None

@router.post("/bank-sms")
async def bank_sms_webhook(payload: BankSMSPayload, db: Session = Depends(get_db)):
    """[12.2] Bank SMS Listener. Auto-verifies bookings if UTR matches."""
    parsed = parse_bank_sms(payload.text)
    if not parsed:
        return {"status": "ignored", "reason": "No UTR found"}
        
    utr = parsed["utr"]
    amount = parsed["amount"]
    
    # [21.7] Idempotency for SMS
    existing_tx = db.query(BankTransaction).filter(BankTransaction.utr_number == utr).first()
    if existing_tx and existing_tx.status == "PROCESSED":
        return {"status": "accepted", "message": "Duplicate UTR (Idempotent).", "is_replay": True}

    booking = db.query(Booking).filter(Booking.utr_number == utr).first()
    if booking and booking.escrow_status == EscrowStatus.UTR_SUBMITTED:
        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "Auto-verified via Bank SMS."
        
        # Record Transaction
        tx = BankTransaction(utr_number=utr, amount=amount, raw_sms=payload.text, status="PROCESSED")
        db.add(tx)
        
        audit = AuditLog(entity_type="Booking", entity_id=booking.id, action="AUTO_VERIFY_SMS", 
                         old_value="UTR_SUBMITTED", new_value="VERIFIED", 
                         performed_by="SYSTEM_SMS_BOT", reason=f"UTR {utr} matched SMS.")
        db.add(audit)
        db.commit()
        return {"status": "verified", "booking_id": booking.id}
            
    return {"status": "accepted", "matched": bool(booking)}

@router.post("/payment-simulate")
async def payment_webhook_handler(
    payload: PaymentWebhook, 
    db: Session = Depends(get_db),
    client_ip: str = Depends(verify_ip),
    authenticated: bool = Depends(signature_guard) # [30.3]
):
    """
    Simulated payment webhook handler.
    [21.3] Idempotency Check using event_id.
    [21.2] Distributed Locking with automatic release.
    [24.3] Fuzzy UTR Matching.
    """
    from services.multi_layer_cache import multi_layer_cache
    from utils.payments import standardize_utr
    await multi_layer_cache.initialize()
    
    # [24.3] Standardize incoming UTR
    payload.utr_number = standardize_utr(payload.utr_number)
    
    # Unique identifier for this logical event
    event_ref = payload.event_id or f"utr_{payload.utr_number}"
    lock_key = f"lock:webhook:{event_ref}"
    
    if multi_layer_cache.redis:
        acquired = await multi_layer_cache.redis.set(lock_key, "locked", ex=30, nx=True)
        if not acquired:
            raise HTTPException(status_code=429, detail="Processing in progress.")

    try:
        # 1. Idempotency Check (Subtask 21.3)
        if payload.event_id:
            existing = db.query(BankTransaction).filter(BankTransaction.event_id == payload.event_id).first()
            if existing:
                return {"status": "accepted", "message": "Already processed.", "is_replay": True}

        # 2. Matching Logic
        booking = None
        if payload.booking_id:
            booking = db.query(Booking).filter(Booking.id == payload.booking_id).first()
        
        if not booking and payload.session_code:
            pay_session = db.query(PaymentSession).filter(PaymentSession.session_code == payload.session_code).first()
            if pay_session:
                booking = db.query(Booking).filter(
                    Booking.user_id == pay_session.user_id,
                    Booking.route_id == pay_session.route_id,
                    Booking.escrow_status == EscrowStatus.CREATED
                ).first()

        if not booking:
            raise HTTPException(status_code=404, detail="No matching booking found.")

        # 3. Process Payment (Subtask 21.4 - Atomic)
        booking.utr_number = payload.utr_number
        
        tx = BankTransaction(
            utr_number=payload.utr_number, 
            amount=payload.amount, 
            event_id=payload.event_id,
            status="PROCESSED"
        )
        db.add(tx)

        if booking.service_type == "UNLOCK":
            UnlockService.fulfill_unlock(db, booking.id)
        else:
            # [26.3] Use centralized transition
            booking.update_escrow_status(
                db, 
                EscrowStatus.VERIFIED, 
                message="Payment verified by webhook.",
                performed_by="WEBHOOK_PROVIDER",
                reason=f"UTR: {payload.utr_number}"
            )
        
        db.commit()
        return {"status": "accepted", "message": "Payment processed successfully."}

    finally:
        # [21.2] Release Lock
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.delete(lock_key)
