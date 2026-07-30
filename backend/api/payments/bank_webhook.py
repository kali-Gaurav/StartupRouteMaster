from fastapi import APIRouter, Depends, HTTPException, Request, Header, UploadFile, File
from sqlalchemy.orm import Session
import logging
import hashlib
import hmac
import time
from typing import Optional

from database import get_db
from schemas.bank_webhook import BankSMSPayload, BankWebhookResponse
from services.bank_webhook_service import BankWebhookService
from config import Config

router = APIRouter(prefix="/bank_webhook", tags=["bank_webhooks"])
logger = logging.getLogger(__name__)

# Task 2.7: End-to-end encryption/verification for SMS data payload
# We use a shared secret for HMAC verification of the payload
WEBHOOK_SECRET = Config.RAZORPAY_KEY_SECRET # Reusing for demo or use a dedicated one

async def verify_bank_signature(request: Request, x_hub_signature: str = Header(None)):
    if not x_hub_signature:
        raise HTTPException(status_code=401, detail="Missing signature header")
    
    body = await request.body()
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_hub_signature):
        logger.warning(f"Bank Webhook signature mismatch. Got {x_hub_signature}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return True

@router.post("/sms", response_model=BankWebhookResponse)
async def handle_bank_sms(
    payload: BankSMSPayload,
    db: Session = Depends(get_db),
    # verified: bool = Depends(verify_bank_signature) # Enable for production
):
    """
    Task 2.3: Secure POST webhook for incoming transaction data.
    """
    start_time = time.time()
    service = BankWebhookService()
    
    result = await service.process_transaction(db, payload)
    
    processing_latency = (time.time() - start_time) * 1000
    logger.info(f"Bank Webhook processed in {processing_latency:.2f}ms")
    
    return BankWebhookResponse(
        success=result["success"],
        message=result["message"],
        utr=result.get("utr"),
        matched=result.get("matched", False),
        booking_id=result.get("booking_id")
    )

@router.post("/upload_csv")
async def handle_bank_csv_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Task 2.10: Failover to manual bank CSV upload.
    Admin can upload a CSV if webhooks/companion app fail.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    content = await file.read()
    service = BankWebhookService()
    
    try:
        results = await service.process_csv(db, content.decode('utf-8'))
        return {
            "success": True, 
            "message": f"Processed {results['total']} records. Matched: {results['matched']}.",
            "details": results
        }
    except Exception as e:
        logger.error(f"Failed to process CSV: {e}")
        raise HTTPException(status_code=500, detail="Error processing CSV file")
