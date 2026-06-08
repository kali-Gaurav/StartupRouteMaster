"""Razorpay Webhook Handler"""

import hmac, hashlib, logging, json
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from database.infrastructure.session import get_db
from services.booking_service import PaymentService
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

def verify_razorpay_signature(payload: str, signature: str) -> bool:
    """Verify Razorpay webhook signature"""
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return False
    generated = hmac.new(webhook_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return generated == signature

@router.post("/razorpay")
async def handle_razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Razorpay webhook events"""
    try:
        body = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        
        if not verify_razorpay_signature(body.decode(), signature):
            logger.error("Invalid Razorpay signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        event_data = json.loads(body)
        event_type = event_data.get("event", "")
        payload = event_data.get("payload", {})
        
        logger.info(f"Razorpay webhook: {event_type}")
        
        if event_type == "payment.authorized":
            payment_data = payload.get("payment", {})
            order_id = payment_data.get("order_id")
            payment = PaymentService.get_payment_by_razorpay_order(db, order_id)
            if payment:
                PaymentService.confirm_payment(
                    db=db,
                    payment_id=payment.id,
                    razorpay_payment_id=payment_data.get("id"),
                    razorpay_signature=payload.get("signature", ""),
                )
        
        return {"status": "received"}
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
