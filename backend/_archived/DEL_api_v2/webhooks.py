from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Booking, PaymentSession, EscrowStatus, AuditLog, BankTransaction
from services.unlock_service import UnlockService
from utils.security import signature_guard 
from utils.responses import success_response, v3_response
from pydantic import BaseModel
from typing import Optional, Dict, Any, cast
import logging
from datetime import datetime
import re

logger = logging.getLogger("api.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Payments & Reconciliation"])

TRUSTED_WEBHOOK_IPS = {"127.0.0.1", "::1"} 

def verify_ip(request: Request):
    """Strict IP Source Validation."""
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip: client_ip = client_ip.split(",")[0].strip()
    
    if client_ip not in TRUSTED_WEBHOOK_IPS:
        logger.warning(f"UNAUTHORIZED_WEBHOOK_ATTEMPT | IP: {client_ip}")
        raise HTTPException(status_code=403, detail="Unauthorized source IP.")
    return client_ip

class PaymentWebhook(BaseModel):
    utr_number: str
    amount: float
    event_id: Optional[str] = None 
    session_code: Optional[str] = None 
    booking_id: Optional[str] = None
    status: str = "SUCCESS"

class BankSMSPayload(BaseModel):
    sender: str
    text: str
    received_at: Optional[datetime] = None

def parse_bank_sms(text: str) -> Optional[Dict[str, Any]]:
    """Regex-parse common Bank SMS templates for UTR and Amount."""
    utr_match = re.search(r'\b(\d{12})\b', text)
    amt_match = re.search(r'(?:Rs|Amt|INR)\.?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if utr_match:
        utr = utr_match.group(1)
        amt = float(amt_match.group(1).replace(',', '')) if amt_match else 0.0
        return {"utr": utr, "amount": amt}
    return None

class SupabaseAuthPayload(BaseModel):
    type: str 
    record: Optional[Dict[str, Any]] = None
    old_record: Optional[Dict[str, Any]] = None

@router.post("/supabase-auth")
async def supabase_auth_webhook(
    payload: SupabaseAuthPayload, 
    db: Session = Depends(get_db),
    client_ip: str = Depends(verify_ip)
):
    """Syncs verification status and profile data from auth.users."""
    from services.auth.user import UserService
    user_service = UserService(db)
    
    if payload.type in ("INSERT", "UPDATE"):
        record = payload.record or {}
        if not record:
            return success_response(data={"status": "ignored", "reason": "No record data provided"})

        sb_id = record.get("id")
        if not sb_id:
            return success_response(data={"status": "ignored", "reason": "No Supabase ID found"})

        email = record.get("email")
        phone = record.get("phone")
        email_confirmed = record.get("email_confirmed_at") is not None
        phone_confirmed = record.get("phone_confirmed_at") is not None
        is_verified = email_confirmed or phone_confirmed
        confirmed_at = record.get("email_confirmed_at") or record.get("phone_confirmed_at")
        
        user = user_service.get_user_by_firebase_uid(str(sb_id))
        if not user and email:
            user = user_service.get_user_by_email(email)
            if user: user.firebase_uid = sb_id
        
        if not user:
            user_data = {
                "firebase_uid": sb_id,
                "email": email,
                "phone_number": phone,
                "is_verified": is_verified,
                "verified_at": confirmed_at,
                "role": record.get("raw_user_meta_data", {}).get("role", "user")
            }
            user = user_service.create_user_with_data(user_data)
        else:
            setattr(user, "is_verified", is_verified)
            setattr(user, "verified_at", confirmed_at)
            if email: user.email = email
            if phone: user.phone_number = phone
        
        db.commit()
        logger.info(f"FIREBASE_AUTH_SYNC | {sb_id} | Verified: {is_verified}")
    
    return success_response(data={"status": "success"})

@router.post("/bank-sms")
async def bank_sms_webhook(payload: BankSMSPayload, db: Session = Depends(get_db)):
    """Bank SMS Listener. Auto-verifies bookings if UTR matches."""
    parsed = parse_bank_sms(payload.text)
    if not parsed:
        return success_response(data={"status": "ignored", "reason": "No UTR found"})
        
    utr = parsed["utr"]
    amount = parsed["amount"]
    
    existing_tx = db.query(BankTransaction).filter(BankTransaction.utr_number == utr).first()
    if existing_tx is not None:
        if getattr(existing_tx, "status", None) == "PROCESSED":
            return success_response(data={"status": "accepted", "message": "Duplicate UTR (Idempotent).", "is_replay": True})

    booking = db.query(Booking).filter(Booking.utr_number == utr).first()
    if booking is not None and getattr(booking, "escrow_status", None) == EscrowStatus.UTR_SUBMITTED:
        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "Auto-verified via Bank SMS."
        
        tx = BankTransaction(utr_number=utr, amount=amount, raw_sms=payload.text, status="PROCESSED")
        db.add(tx)
        
        audit = AuditLog(entity_type="Booking", entity_id=booking.id, action="AUTO_VERIFY_SMS", 
                         old_value="UTR_SUBMITTED", new_value="VERIFIED", 
                         performed_by="SYSTEM_SMS_BOT", reason=f"UTR {utr} matched SMS.")
        db.add(audit)
        db.commit()
        logger.info(f"BANK_SMS_VERIFIED | {booking.id} | UTR: {utr}")
        return success_response(data={"status": "verified", "booking_id": booking.id})
            
    return success_response(data={"status": "accepted", "matched": bool(booking)})

@router.post("/payment-simulate")
async def payment_webhook_handler(
    payload: PaymentWebhook, 
    db: Session = Depends(get_db),
    client_ip: str = Depends(verify_ip),
    authenticated: bool = Depends(signature_guard) 
):
    """Simulated payment webhook handler."""
    from services.multi_layer_cache import multi_layer_cache
    from utils.payments import standardize_utr
    await multi_layer_cache.initialize()
    
    payload.utr_number = standardize_utr(payload.utr_number)
    event_ref = payload.event_id or f"utr_{payload.utr_number}"
    lock_key = f"lock:webhook:{event_ref}"
    
    if multi_layer_cache.redis:
        acquired = await multi_layer_cache.redis.set(lock_key, "locked", ex=30, nx=True)
        if not acquired:
            raise HTTPException(status_code=429, detail="Processing in progress.")

    try:
        if payload.event_id:
            existing = db.query(BankTransaction).filter(BankTransaction.event_id == payload.event_id).first()
            if existing:
                return success_response(data={"status": "accepted", "message": "Already processed.", "is_replay": True})

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
            logger.error(f"WEBHOOK_MATCH_FAILED | UTR: {payload.utr_number} | Session: {payload.session_code}")
            raise HTTPException(status_code=404, detail="No matching booking found.")

        setattr(booking, "utr_number", payload.utr_number)
        
        tx = BankTransaction(
            utr_number=payload.utr_number, 
            amount=payload.amount, 
            event_id=payload.event_id,
            status="PROCESSED"
        )
        db.add(tx)

        if booking.service_type == "UNLOCK":
            UnlockService.fulfill_unlock(db, cast(str, booking.id))
        else:
            booking.update_escrow_status(
                db, 
                EscrowStatus.VERIFIED, 
                message="Payment verified by webhook.",
                performed_by="WEBHOOK_PROVIDER",
                reason=f"UTR: {payload.utr_number}"
            )
        
        db.commit()
        logger.info(f"PAYMENT_WEBHOOK_SUCCESS | {booking.id} | UTR: {payload.utr_number}")
        return success_response(data={"status": "accepted", "message": "Payment processed successfully."})

    finally:
        if multi_layer_cache.redis:
            await multi_layer_cache.redis.delete(lock_key)
